"""
Tests for remediation/ — Quiz scoring, deterministic diagnosis, and style selector.
"""
import os
import pytest

os.environ.setdefault("LLM_MODE", "real")

from unittest.mock import patch
from slice.store import Store
from slice.config import Settings
from remediation.flow import score_quiz, select_style, count_revisions, styles_tried_for_concept
from remediation.questions import ANSWER_KEY, QUIZ_QUESTIONS, ALL_CONCEPTS, get_retest_question
from remediation.provider import RealLLMExplanationProvider, get_provider
from remediation.schema import QuizSubmission, Diagnosis, Outcome, ExplanationPayload
from slice.budget import Budget


def _settings() -> Settings:
    return Settings(
        api_key="",
        model="test",
        fallback_model="",
        escalation_model="",
        max_tokens=100,
        max_tokens_per_run=250000,
        max_attempts_per_step=3,
        expert_timeout_minutes=45,
        llm_mode="real",
    )


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


class TestQuizScoring:
    def test_all_correct(self):
        answers = dict(ANSWER_KEY)
        wrong, failed, passed = score_quiz(answers)
        assert wrong == []
        assert failed == []
        assert set(passed) == set(ALL_CONCEPTS)

    def test_one_wrong(self):
        answers = dict(ANSWER_KEY)
        answers["Q5"] = "a"  # Wrong: correct is "b"
        wrong, failed, passed = score_quiz(answers)
        assert "Q5" in wrong
        assert "call_stack" in failed
        assert "call_stack" not in passed

    def test_multiple_wrong_same_concept(self):
        answers = dict(ANSWER_KEY)
        answers["Q5"] = "a"
        answers["Q6"] = "a"
        wrong, failed, passed = score_quiz(answers)
        assert len(wrong) == 2
        assert failed.count("call_stack") == 1  # deduplicated

    def test_multiple_concepts_wrong(self):
        answers = dict(ANSWER_KEY)
        answers["Q5"] = "a"  # call_stack wrong
        answers["Q7"] = "c"  # return_propagation wrong
        wrong, failed, passed = score_quiz(answers)
        assert "call_stack" in failed
        assert "return_propagation" in failed
        assert "base_case" in passed
        assert "recursive_step" in passed

    def test_case_insensitive_scoring(self):
        answers = {q: ANSWER_KEY[q].upper() for q in ANSWER_KEY}
        wrong, failed, passed = score_quiz(answers)
        assert wrong == []


class TestStyleSelection:
    def test_default_when_no_history(self, store):
        style, reason = select_style(store, "new_student", "call_stack", [])
        assert style == "analogy"
        assert "no prior data" in reason

    def test_switch_after_failure(self, store):
        style, reason = select_style(store, "student", "call_stack", ["analogy"])
        assert style == "trace"
        assert "switching to trace" in reason

    def test_population_level_selection(self, store):
        # Seed population data via intervention_history: trace wins more for call_stack
        store.record_intervention("s1", "call_stack", "analogy", 1, False)
        store.record_intervention("s2", "call_stack", "trace", 1, True)
        store.record_intervention("s3", "call_stack", "trace", 1, True)

        style, reason = select_style(store, "new_student", "call_stack", [])
        assert style == "trace"

    def test_student_history_takes_priority(self, store):
        # Population says trace is better
        store.record_intervention("other", "call_stack", "trace", 1, True)
        store.record_intervention("other", "call_stack", "trace", 1, True)
        # But this student previously succeeded with analogy
        store.record_intervention("target_student", "call_stack", "analogy", 1, True)

        style, reason = select_style(store, "target_student", "call_stack", [])
        assert style == "analogy"


class TestRealLLMProvider:
    def test_real_provider_calls_llm(self, store):
        run_id = store.create_run("test")
        s = _settings()
        b = Budget(store, run_id, s)
        provider = get_provider()
        with patch("slice.llm.complete") as patched_complete:
            patched_complete.return_value = ExplanationPayload(
                student_id="test_student",
                concept="call_stack",
                style="analogy",
                text="Think of the call stack like cafeteria trays."
            )
            result = provider.explain(
                student_id="test_student",
                concept="call_stack",
                style="analogy",
                wrong_answer="a",
                correct_answer="b",
                question_text="How many frames?",
                budget=b,
                settings=s,
            )
            assert result.concept == "call_stack"
            assert result.style == "analogy"
            assert "cafeteria trays" in result.text
            assert patched_complete.called

    def test_real_provider_trace_style(self, store):
        run_id = store.create_run("test")
        s = _settings()
        b = Budget(store, run_id, s)
        provider = get_provider()
        with patch("slice.llm.complete") as patched_complete:
            patched_complete.return_value = ExplanationPayload(
                student_id="test_student",
                concept="call_stack",
                style="trace",
                text="Let's trace step by step."
            )
            result = provider.explain(
                student_id="test_student",
                concept="call_stack",
                style="trace",
                wrong_answer="a",
                correct_answer="b",
                question_text="How many frames?",
                budget=b,
                settings=s,
            )
            assert result.style == "trace"
            assert "trace" in result.text.lower() or "step" in result.text.lower()


class TestEnrichedPromptConstruction:
    def test_real_llm_formats_options_and_attempts(self, monkeypatch, store):
        from remediation.provider import RealLLMExplanationProvider
        from remediation.schema import ExplanationPayload

        captured_messages = []

        def mock_complete(*, settings, budget, messages, schema, step, **kwargs):
            captured_messages.extend(messages)
            return ExplanationPayload(
                student_id="priya",
                concept="call_stack",
                style="analogy",
                text="Trays analogy with 5 frames.",
            )

        import slice.llm
        monkeypatch.setattr(slice.llm, "complete", mock_complete)

        run_id = store.create_run("test")
        s = _settings()
        b = Budget(store, run_id, s)
        provider = RealLLMExplanationProvider()

        result = provider.explain(
            student_id="priya",
            concept="call_stack",
            style="analogy",
            wrong_answer="a",
            correct_answer="b",
            question_text="What is the maximum number of activation records for factorial(4)?",
            budget=b,
            settings=s,
            options={"a": "4", "b": "5", "c": "3", "d": "1"},
            attempt=2,
            mastery_pct=25,
            previous_styles=["trace"],
            topic="CS310 — Recursion",
        )

        assert result.text == "Trays analogy with 5 frames."
        assert len(captured_messages) == 2

        user_msg = captured_messages[1]["content"]
        assert "[A] 4  <-- [STUDENT'S WRONG CHOICE]" in user_msg
        assert "[B] 5  <-- [CORRECT ANSWER]" in user_msg
        assert "Remediation Attempt: 2 of 2" in user_msg
        assert "Styles already tried that failed: Trace" in user_msg
        assert "Student's Current Concept Mastery: 25%" in user_msg
        assert "Call Stack" in user_msg
        assert "Diagnostic Question:" in user_msg


class TestQuestionBank:
    def test_eight_questions(self):
        assert len(QUIZ_QUESTIONS) == 8

    def test_two_per_concept(self):
        from collections import Counter
        concepts = Counter(q.concept for q in QUIZ_QUESTIONS)
        for c in ALL_CONCEPTS:
            assert concepts[c] == 2, f"Expected 2 questions for {c}, got {concepts[c]}"

    def test_retest_questions_exist(self):
        for c in ALL_CONCEPTS:
            q1 = get_retest_question(c, 1)
            q2 = get_retest_question(c, 2)
            assert q1.concept == c
            assert q2.concept == c
            assert q1.text != q2.text  # Different variant

    def test_all_questions_have_correct_answer(self):
        for q in QUIZ_QUESTIONS:
            assert q.correct in q.options
