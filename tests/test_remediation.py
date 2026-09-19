"""
Tests for remediation/ — Quiz scoring, deterministic diagnosis, and style selector.
"""
import os
import pytest

os.environ.setdefault("LLM_MODE", "mock")

from slice.store import Store
from slice.config import Settings
from remediation.flow import score_quiz, select_style, count_revisions, styles_tried_for_concept
from remediation.questions import ANSWER_KEY, QUIZ_QUESTIONS, ALL_CONCEPTS, get_retest_question
from remediation.provider import MockExplanationProvider
from remediation.schema import QuizSubmission, Diagnosis, Outcome
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
        llm_mode="mock",
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
        # Seed population data: trace wins more for call_stack
        r1 = store.create_run("test")
        store.append(r1, "outcome", Outcome(
            student_id="s1", concept="call_stack", style="analogy",
            passed=False, total_attempts=1).model_dump(), "sys")
        r2 = store.create_run("test")
        store.append(r2, "outcome", Outcome(
            student_id="s2", concept="call_stack", style="trace",
            passed=True, total_attempts=1).model_dump(), "sys")
        r3 = store.create_run("test")
        store.append(r3, "outcome", Outcome(
            student_id="s3", concept="call_stack", style="trace",
            passed=True, total_attempts=1).model_dump(), "sys")

        style, reason = select_style(store, "new_student", "call_stack", [])
        assert style == "trace"

    def test_student_history_takes_priority(self, store):
        # Population says trace is better
        r1 = store.create_run("test")
        store.append(r1, "outcome", Outcome(
            student_id="other", concept="call_stack", style="trace",
            passed=True, total_attempts=1).model_dump(), "sys")
        r2 = store.create_run("test")
        store.append(r2, "outcome", Outcome(
            student_id="other", concept="call_stack", style="trace",
            passed=True, total_attempts=1).model_dump(), "sys")
        # But this student previously succeeded with analogy
        r3 = store.create_run("test")
        store.append(r3, "outcome", Outcome(
            student_id="target_student", concept="call_stack", style="analogy",
            passed=True, total_attempts=1).model_dump(), "sys")

        style, reason = select_style(store, "target_student", "call_stack", [])
        assert style == "analogy"


class TestMockProvider:
    def test_mock_returns_explanation(self, store):
        run_id = store.create_run("test")
        s = _settings()
        b = Budget(store, run_id, s)
        provider = MockExplanationProvider()
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

    def test_mock_trace_style(self, store):
        run_id = store.create_run("test")
        s = _settings()
        b = Budget(store, run_id, s)
        provider = MockExplanationProvider()
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
