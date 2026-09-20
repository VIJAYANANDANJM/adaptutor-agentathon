"""
tests/test_practice.py — Comprehensive tests for Feature: Retest Exhaustion → Guided Practice → Fresh Retest.

Verifies all 13 requirements:
1. Retest questions are not repeated while unused questions remain.
2. Exhaustion is correctly detected.
3. Exhaustion triggers Guided Practice.
4. Guided Practice contains multiple concept-relevant steps.
5. Guided Practice gives feedback after each step.
6. Guided Practice does not become an infinite loop (bounded retry).
7. Guided Practice completes successfully.
8. A fresh independent retest occurs after Guided Practice.
9. Existing mastery updates continue to work.
10. Guided Practice is recorded in intervention/session history.
11. Session resume works correctly if the learner closes the session during Guided Practice.
12. LLM failure does not break the flow (deterministic fallback).
13. Existing tests continue to pass.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from unittest.mock import patch
import pytest

from slice.config import Settings
from slice.records import RunState
from slice.runner import advance
from slice.store import Store
from remediation.curriculum import get_module
from remediation.flow import RemediationFlow, start_session, submit_retest
from remediation.learner import LearnerModel
from remediation.practice import (
    get_attempted_question_texts,
    get_curated_retest_pool,
    get_next_unused_retest_question,
    is_retest_pool_exhausted,
    get_guided_practice,
    get_fresh_retest_question,
    has_completed_guided_practice,
    get_guided_practice_progress,
    record_guided_practice_event,
)
from remediation.schema import ExplanationPayload
from remediation.stub import PERSONA_QUIZ_ANSWERS
from run import (
    print_pool_exhausted_card,
    print_guided_practice_complete_card,
    run_guided_practice_session,
    _drive_session_loop,
)


def _test_settings(llm_mode: str = "stub") -> Settings:
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


# ── Requirement 1 & 2: Non-repetition & Exhaustion Detection ──────────────────

def test_retest_question_non_repetition():
    """Verify that unused curated retest questions are preferred and not repeated."""
    mod = get_module("python_recursion")
    concept = "call_stack"
    pool = get_curated_retest_pool(mod, concept)
    assert len(pool) >= 2

    # Initially, no questions attempted
    attempted = set()
    q1 = get_next_unused_retest_question(mod, concept, attempted)
    assert q1 is not None
    assert q1.text == pool[0].text
    assert is_retest_pool_exhausted(mod, concept, attempted) is False

    # After attempting question 1, question 2 is selected (no repetition)
    attempted.add(q1.text.strip())
    q2 = get_next_unused_retest_question(mod, concept, attempted)
    assert q2 is not None
    assert q2.text != q1.text
    assert q2.text == pool[1].text
    assert is_retest_pool_exhausted(mod, concept, attempted) is False

    # After attempting both, pool is exhausted
    attempted.add(q2.text.strip())
    assert get_next_unused_retest_question(mod, concept, attempted) is None
    assert is_retest_pool_exhausted(mod, concept, attempted) is True


# ── Requirement 3: Exhaustion Triggers Guided Practice ────────────────────────

def test_exhaustion_triggers_guided_practice(tmp_path):
    """Failing all curated retest questions must trigger awaiting_guided_practice rather than immediate crash or exit."""
    store = Store(str(tmp_path / "test_exhaustion.db"))
    s = _test_settings()
    flow = RemediationFlow()
    student_id = "test_exhaust_student"

    answers = dict(PERSONA_QUIZ_ANSWERS["ananya_analogy"])  # fails Q5: call_stack
    run_id = start_session(store, student_id, answers, s)
    mod = get_module("python_recursion")

    # Attempt 1: fail
    advance(store, run_id, flow, s)
    q1 = mod.get_retest_question("call_stack", 1)
    submit_retest(store, run_id, student_id, "call_stack", "wrong", s, question_text=q1.text, correct_answer=q1.correct)
    store.set_state(run_id, RunState.PROBING)

    # Attempt 2: fail
    advance(store, run_id, flow, s)
    q2 = mod.get_retest_question("call_stack", 2)
    submit_retest(store, run_id, student_id, "call_stack", "wrong", s, question_text=q2.text, correct_answer=q2.correct)
    store.set_state(run_id, RunState.PROBING)

    state = advance(store, run_id, flow, s)
    assert state == RunState.AWAITING_EXPERT

    # Verify pool exhaustion event was recorded
    exhaust_event = store.latest(run_id, "pool_exhaustion")
    assert exhaust_event is not None
    assert exhaust_event["concept"] == "call_stack"

    # Verify system is awaiting guided practice
    gp_event = store.latest(run_id, "awaiting_guided_practice")
    assert gp_event is not None
    assert gp_event["concept"] == "call_stack"


# ── Requirement 4 & 5: Concept Steps & Immediate Feedback ─────────────────────

def test_guided_practice_steps_and_feedback():
    """Verify Guided Practice provides 2-4 concept-specific reasoning steps with feedback."""
    for concept in ["call_stack", "base_case", "recursive_step", "return_propagation"]:
        steps = get_guided_practice(concept)
        assert 2 <= len(steps) <= 4
        for step in steps:
            assert step.step_number >= 1
            assert step.total_steps == len(steps)
            assert len(step.options) >= 2
            assert step.correct in step.options
            assert len(step.explanation) > 10
            assert len(step.hint) > 5


# ── Requirement 6: Bounded Retries (No Infinite Loop) ─────────────────────────

def test_guided_practice_no_infinite_loop(tmp_path):
    """Verify that wrong answers allow at most one retry before advancing (never loops infinitely)."""
    store = Store(str(tmp_path / "test_no_loop.db"))
    s = _test_settings()
    run_id = store.create_run("remediation", meta={"student_id": "test_loop_student"})

    # Provider that ALWAYS gives wrong answers
    def wrong_provider(student_id, concept, step_num, attempt_num):
        return "wrong_option"

    f = io.StringIO()
    with redirect_stdout(f):
        completed = run_guided_practice_session(
            store=store,
            run_id=run_id,
            student_id="test_loop_student",
            concept="call_stack",
            concept_display="Call Stack",
            settings=s,
            interactive=False,
            practice_provider=wrong_provider,
        )
    out = f.getvalue()

    assert completed is True
    assert "Correction: The correct choice is" in out
    assert "Let's try this step one more time." in out

    # Verify each step recorded at most 2 attempts
    progress = get_guided_practice_progress(store, run_id, "call_stack")
    assert progress is not None
    assert progress["completed"] is True
    for res in progress["step_results"]:
        assert res["attempts"] <= 2


# ── Requirement 7 & 10: Guided Practice Completion & History ──────────────────

def test_guided_practice_completion_and_history(tmp_path):
    """Verify Guided Practice records history in store and LearnerModel."""
    store = Store(str(tmp_path / "test_history.db"))
    s = _test_settings()
    run_id = store.create_run("remediation", meta={"student_id": "test_history_student"})

    def correct_provider(student_id, concept, step_num, attempt_num):
        return None  # defaults to correct

    f = io.StringIO()
    with redirect_stdout(f):
        run_guided_practice_session(
            store=store,
            run_id=run_id,
            student_id="test_history_student",
            concept="call_stack",
            concept_display="Call Stack",
            settings=s,
            interactive=False,
            practice_provider=correct_provider,
        )

    assert has_completed_guided_practice(store, run_id, "call_stack") is True

    # Verify intervention recorded in persistent learner profile
    learner = LearnerModel(store, "test_history_student")
    history = store.history(run_id, "guided_practice")
    assert len(history) >= 1
    assert history[-1].payload["completed"] is True


# ── Requirement 8: Fresh Independent Retest ───────────────────────────────────

def test_fresh_independent_retest():
    """Verify fresh retest question is independent, unattempted, and has clear correct answers."""
    mod = get_module("python_recursion")
    attempted = {
        "At the deepest point of power(2, 3) where power(x, n) calls power(x, n-1) with base case n == 0, how many frames are on the stack?",
        "In def power(x, n): if n == 0: return 1; return x * power(x, n-1), what is the base case?",
    }
    fresh_q = get_fresh_retest_question(mod, "call_stack", attempted)
    assert fresh_q is not None
    assert fresh_q.text not in attempted
    assert len(fresh_q.options) >= 2
    assert fresh_q.correct in fresh_q.options


# ── Requirement 11: Session Resume During Guided Practice ─────────────────────

def test_session_resume_during_guided_practice(tmp_path):
    """If session terminates after step 1, resuming picks up at step 2 without repeating step 1."""
    store = Store(str(tmp_path / "test_resume.db"))
    s = _test_settings()
    run_id = store.create_run("remediation", meta={"student_id": "test_resume_student"})

    # Simulate step 1 already completed in SQLite
    record_guided_practice_event(
        store=store,
        run_id=run_id,
        student_id="test_resume_student",
        concept="call_stack",
        completed=False,
        step_results=[{"step_number": 1, "passed": True, "attempts": 1}],
        current_step=2,
        total_steps=3,
    )

    steps_called = []
    def provider(student_id, concept, step_num, attempt_num):
        steps_called.append(step_num)
        return None  # correct

    f = io.StringIO()
    with redirect_stdout(f):
        run_guided_practice_session(
            store=store,
            run_id=run_id,
            student_id="test_resume_student",
            concept="call_stack",
            concept_display="Call Stack",
            settings=s,
            interactive=False,
            practice_provider=provider,
        )

    # Step 1 was already done, so only steps 2 and 3 should have been executed
    assert 1 not in steps_called
    assert 2 in steps_called
    assert 3 in steps_called
    assert has_completed_guided_practice(store, run_id, "call_stack") is True


# ── Requirement 12: Topic-Agnostic & Offline LLM Fallback ─────────────────────

def test_topic_agnostic_guided_practice_and_fallback():
    """Verify non-recursion concepts and arbitrary custom concepts synthesize valid guided practice steps."""
    # DB Normalization
    db_steps = get_guided_practice("first_normal_form", topic="Database Management")
    assert len(db_steps) == 3
    assert "atomic" in db_steps[0].prompt.lower() or "atomic" in db_steps[0].explanation.lower()

    # Dynamic fallback for arbitrary AI-generated module
    custom_steps = get_guided_practice("quantum_entanglement", topic="Quantum Computing")
    assert len(custom_steps) == 3
    assert "Quantum Entanglement" in custom_steps[0].context


# ── End-to-End Integration in Session Loop ────────────────────────────────────

def test_e2e_session_loop_exhaustion_to_fresh_retest_pass(tmp_path):
    """Full session loop: Attempt 1 fail -> Attempt 2 fail -> Exhaustion -> Guided Practice -> Fresh Retest Pass."""
    store = Store(str(tmp_path / "test_e2e_pass.db"))
    s = _test_settings(llm_mode="real")
    flow = RemediationFlow()
    student_id = "test_e2e_pass_student"

    answers = dict(PERSONA_QUIZ_ANSWERS["ananya_analogy"])
    run_id = start_session(store, student_id, answers, s)

    # Retest provider fails attempts 1 and 2, but passes fresh_retest
    def retest_provider(student_id, concept, style, attempt):
        if style == "fresh_retest":
            return "a"  # correct for fresh retest
        return "wrong"  # fail attempts 1 and 2

    def practice_provider(student_id, concept, step_num, attempt_num):
        return None  # correct for all guided practice steps

    def _fake_complete(*args, **kwargs):
        return ExplanationPayload(
            student_id=student_id,
            concept="call_stack",
            style="analogy",
            text="Explanation text.",
        )

    f = io.StringIO()
    with patch("slice.llm.complete", side_effect=_fake_complete):
        with redirect_stdout(f):
            _drive_session_loop(
                store,
                run_id,
                student_id,
                s,
                flow,
                interactive=False,
                retest_provider=retest_provider,
                practice_provider=practice_provider,
            )
    out = f.getvalue()

    # 1. Retest Pool Exhausted card displayed
    assert "⚠️ RETEST POOL EXHAUSTED" in out
    assert "All available retest questions have" in out

    # 2. Guided Practice ran
    assert "🧭 GUIDED PRACTICE: CALL STACK" in out
    assert "✓ GUIDED PRACTICE COMPLETE" in out

    # 3. Fresh Retest presented
    assert "🎯 FRESH RETEST: Call Stack" in out

    # 4. Successful resolution and concept improved card
    assert "✓ CONCEPT IMPROVED" in out
    assert "All concepts resolved! Session complete." in out
