"""
Tests for Feature: Mistake-Specific Feedback After a Failed Retest.

Verifies:
1. Failed retest generates a RetestFeedback record.
2. The feedback receives the actual selected option text.
3. The feedback receives the correct option text.
4. The feedback addresses the specific mistake / misconception.
5. Adaptive intervention selection (backward loop) continues after feedback.
6. A correct retest does NOT emit mistake feedback.
7. LLM failure or offline mode engages deterministic fallback without breaking the session.
8. Repeated failures on the same concept generate feedback before escalation.
9. Non-recursion / dynamic modules generate valid feedback.
"""
from __future__ import annotations

import os
from unittest.mock import patch
import pytest

os.environ.setdefault("LLM_MODE", "real")

from slice.config import Settings
from slice.records import RunState
from slice.runner import advance
from slice.store import Store

from remediation.curriculum import get_module
from remediation.feedback import (
    generate_retest_feedback,
    get_deterministic_feedback,
    MistakeAnalysisSchema,
)
from remediation.flow import RemediationFlow, start_session, submit_retest
from remediation.schema import ExplanationPayload, RetestFeedback
from remediation.stub import PERSONA_QUIZ_ANSWERS


def _test_settings(llm_mode: str = "real") -> Settings:
    return Settings(
        api_key="",
        model="test",
        fallback_model="",
        escalation_model="",
        max_tokens=100,
        max_tokens_per_run=250000,
        max_attempts_per_step=3,
        expert_timeout_minutes=45,
        llm_mode=llm_mode,
    )


@pytest.fixture(autouse=True)
def fake_llm_completion():
    """Mock slice.llm.complete to return valid structured responses."""
    with patch("slice.llm.complete") as m:
        def _fake_complete(*args, **kwargs):
            schema = kwargs.get("schema")
            step = kwargs.get("step", "")

            if schema == MistakeAnalysisSchema:
                return MistakeAnalysisSchema(
                    why_wrong="You assumed the recursive call returned immediately instead of pausing on the call stack.",
                    what_to_remember="Stack frames accumulate and only unwind when the base case returns.",
                )

            style = "worked_example" if "worked_example" in step else "analogy"
            concept = "call_stack"
            for c in ["call_stack", "return_propagation", "base_case", "recursive_step", "first_normal_form"]:
                if c in step:
                    concept = c
                    break
            return ExplanationPayload(
                student_id="test_student",
                concept=concept,
                style=style,
                text=f"Explanation for {concept} using {style}.",
            )

        m.side_effect = _fake_complete
        yield m


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test_feedback.db"))
    yield s
    s.close()


def test_failed_retest_produces_mistake_feedback(store):
    """Criterion 1 & 2 & 3: Failed retest generates feedback with selected and correct option text."""
    s = _test_settings()
    flow = RemediationFlow()
    student_id = "student_fail_1"

    # Quiz answers failing only call_stack
    answers = dict(PERSONA_QUIZ_ANSWERS["priya_22cs031"])
    run_id = start_session(store, student_id, answers, s, module_id="python_recursion")

    # Advance to awaiting retest
    state = advance(store, run_id, flow, s)
    assert state == RunState.AWAITING_EXPERT

    mod = get_module("python_recursion")
    retest_q = mod.get_retest_question("call_stack", 1)
    wrong_opt = "a" if retest_q.correct == "b" else "b"
    wrong_text = retest_q.options[wrong_opt]
    correct_text = retest_q.options[retest_q.correct]

    # Student submits WRONG retest answer
    submit_retest(store, run_id, student_id, "call_stack", wrong_opt, s)
    store.set_state(run_id, RunState.PROBING)

    # Advance state machine to evaluate
    next_state = advance(store, run_id, flow, s)

    # 1. Feedback record must exist in store
    feedbacks = store.history(run_id, "retest_feedback")
    assert len(feedbacks) == 1
    fb = feedbacks[0].payload

    # 2. Selected option text must match
    assert fb["selected_option"] == wrong_opt.upper()
    assert fb["selected_text"] == wrong_text

    # 3. Correct option text must match
    assert fb["correct_option"] == retest_q.correct.upper()
    assert fb["correct_text"] == correct_text

    # 4. Feedback must provide targeted explanation
    assert len(fb["why_wrong"]) > 10
    assert len(fb["what_to_remember"]) > 10


def test_correct_retest_does_not_trigger_feedback(store):
    """Criterion 6: A correct retest does NOT produce mistake feedback."""
    s = _test_settings()
    flow = RemediationFlow()
    student_id = "student_pass_1"

    answers = dict(PERSONA_QUIZ_ANSWERS["priya_22cs031"])
    run_id = start_session(store, student_id, answers, s, module_id="python_recursion")

    state = advance(store, run_id, flow, s)
    assert state == RunState.AWAITING_EXPERT

    mod = get_module("python_recursion")
    retest_q = mod.get_retest_question("call_stack", 1)

    # Student submits CORRECT retest answer
    submit_retest(store, run_id, student_id, "call_stack", retest_q.correct, s)
    store.set_state(run_id, RunState.PROBING)

    final_state = advance(store, run_id, flow, s)
    assert final_state == RunState.COMPLETE

    # Zero feedback records should be emitted
    feedbacks = store.history(run_id, "retest_feedback")
    assert len(feedbacks) == 0


def test_adaptation_continues_after_feedback(store):
    """Criterion 5: After feedback is logged, adaptive style selection and next intervention occur."""
    s = _test_settings()
    flow = RemediationFlow()
    student_id = "student_adapt_check"

    answers = dict(PERSONA_QUIZ_ANSWERS["priya_22cs031"])
    run_id = start_session(store, student_id, answers, s, module_id="python_recursion")

    advance(store, run_id, flow, s)
    first_sel = store.latest(run_id, "style_selection")
    first_style = first_sel["selected_style"]

    mod = get_module("python_recursion")
    retest_q = mod.get_retest_question("call_stack", 1)
    wrong_opt = "a" if retest_q.correct == "b" else "b"

    # Retest 1 fails
    submit_retest(store, run_id, student_id, "call_stack", wrong_opt, s)
    store.set_state(run_id, RunState.PROBING)

    advance(store, run_id, flow, s)

    # Feedback was recorded
    assert store.latest(run_id, "retest_feedback") is not None

    # Style selection for attempt 2 occurred
    second_sel = store.latest(run_id, "style_selection")
    assert second_sel["attempt"] == 2
    assert second_sel["selected_style"] != first_style  # Pivoted to alternate style!

    # Explanation for attempt 2 was generated
    explanations = store.history(run_id, "explanation")
    assert len(explanations) == 2


def test_deterministic_fallback_when_llm_fails(store):
    """Criterion 7: LLM failure or error falls back to deterministic feedback without breaking flow."""
    s = _test_settings()
    flow = RemediationFlow()
    student_id = "student_llm_fail"

    answers = dict(PERSONA_QUIZ_ANSWERS["priya_22cs031"])
    run_id = start_session(store, student_id, answers, s, module_id="python_recursion")

    advance(store, run_id, flow, s)
    mod = get_module("python_recursion")
    retest_q = mod.get_retest_question("call_stack", 1)
    wrong_opt = "a" if retest_q.correct == "b" else "b"

    # Simulate LLM raising an exception during feedback generation
    def _fail_feedback(*args, **kwargs):
        if kwargs.get("schema") == MistakeAnalysisSchema:
            raise RuntimeError("OpenRouter Connection Failed")
        return ExplanationPayload(
            student_id="student_llm_fail",
            concept="call_stack",
            style="trace",
            text="Explanation for call_stack using trace.",
        )

    with patch("slice.llm.complete", side_effect=_fail_feedback):
        submit_retest(store, run_id, student_id, "call_stack", wrong_opt, s)
        store.set_state(run_id, RunState.PROBING)

        # Must not crash!
        state = advance(store, run_id, flow, s)
        assert state in (RunState.AWAITING_EXPERT, RunState.PROBING)

        fb = store.latest(run_id, "retest_feedback")
        assert fb is not None
        assert fb["source"] == "fallback"
        assert wrong_opt.upper() in fb["why_wrong"]
        assert fb["selected_text"] in fb["why_wrong"]


def test_repeated_failure_produces_feedback_before_escalation(store):
    """Edge Case: Second attempt failure on the same concept produces feedback before instructor escalation."""
    s = _test_settings()
    flow = RemediationFlow()
    student_id = "student_double_fail"

    answers = dict(PERSONA_QUIZ_ANSWERS["priya_22cs031"])
    run_id = start_session(store, student_id, answers, s, module_id="python_recursion")

    mod = get_module("python_recursion")

    # Retest 1: Fail
    advance(store, run_id, flow, s)
    q1 = mod.get_retest_question("call_stack", 1)
    w1 = "a" if q1.correct == "b" else "b"
    submit_retest(store, run_id, student_id, "call_stack", w1, s)
    store.set_state(run_id, RunState.PROBING)

    # Retest 2: Fail
    advance(store, run_id, flow, s)
    q2 = mod.get_retest_question("call_stack", 2)
    w2 = "a" if q2.correct == "b" else "b"
    submit_retest(store, run_id, student_id, "call_stack", w2, s)
    store.set_state(run_id, RunState.PROBING)

    final_state = advance(store, run_id, flow, s)
    assert final_state == RunState.AWAITING_EXPERT

    # There should be 2 feedback records (one for attempt 1, one for attempt 2)
    feedbacks = store.history(run_id, "retest_feedback")
    assert len(feedbacks) == 2
    assert feedbacks[0].payload["attempt"] == 1
    assert feedbacks[1].payload["attempt"] == 2

    # Escalation flag should be present
    flag = store.latest(run_id, "instructor_flag")
    assert flag is not None
    assert flag["both_failed"] is True


def test_feedback_on_non_recursion_module(store):
    """Edge Case: Multi-module support (db_normalization) produces valid feedback."""
    s = _test_settings()
    flow = RemediationFlow()
    student_id = "student_db_feedback"

    # db_normalization: fail first_normal_form (Q1='a', Q2='a')
    answers = {"Q1": "a", "Q2": "a", "Q3": "a", "Q4": "b", "Q5": "a", "Q6": "b", "Q7": "a", "Q8": "a"}
    run_id = start_session(store, student_id, answers, s, module_id="db_normalization")

    advance(store, run_id, flow, s)

    mod = get_module("db_normalization")
    retest_q = mod.get_retest_question("first_normal_form", 1)
    wrong_opt = "a" if retest_q.correct == "b" else "b"

    submit_retest(store, run_id, student_id, "first_normal_form", wrong_opt, s)
    store.set_state(run_id, RunState.PROBING)

    advance(store, run_id, flow, s)

    fb = store.latest(run_id, "retest_feedback")
    assert fb is not None
    assert fb["concept"] == "first_normal_form"
    assert fb["selected_option"] == wrong_opt.upper()
    assert fb["selected_text"] == retest_q.options[wrong_opt]
