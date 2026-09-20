"""
tests/test_goals.py — Tests for Feature: Clear Learning State and Next Goal.

Verifies:
1. get_learning_goal returns concept-specific pedagogical targets.
2. get_goal_achieved returns concept-specific achievement confirmations.
3. Dynamic fallback functions correctly for unlisted / generated concepts.
4. print_learning_state_card formats first attempt cleanly without fake previous approach.
5. print_learning_state_card formats retry attempt with previous approach ❌, failure result, and next approach.
6. print_concept_improved_card formats mastery delta, goal achieved, and clean next step.
7. Integration with session loop verifies state card and concept improved card execution.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
import pytest

from slice.config import Settings
from slice.records import RunState
from slice.store import Store
from remediation.flow import RemediationFlow, start_session, submit_retest
from remediation.goals import CONCEPT_GOALS, get_learning_goal, get_goal_achieved
from remediation.learner import LearnerModel
from remediation.stub import PERSONA_QUIZ_ANSWERS
from run import (
    print_learning_state_card,
    print_concept_improved_card,
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


# ── Unit Tests: get_learning_goal & get_goal_achieved ─────────────────────────

def test_concept_specific_goals():
    """Verify predefined concepts have rich, non-generic pedagogical goals."""
    for concept in ["call_stack", "base_case", "recursive_step", "return_propagation"]:
        goal = get_learning_goal(concept)
        assert len(goal) > 20
        assert "learn" not in goal.lower() or "understand" in goal.lower() or "identify" in goal.lower()

    # Verify DB, OS, and IoT concepts are covered
    assert "repeating groups" in get_learning_goal("first_normal_form").lower()
    assert "page table" in get_learning_goal("operating_systems_virtual_core_rules").lower()
    assert "publish/subscribe" in get_learning_goal("iot_mqtt_fundamentals").lower()


def test_goal_achieved_messages():
    """Verify achievement messages are specific and encouraging."""
    for concept in ["call_stack", "base_case", "first_normal_form", "iot_mqtt_fundamentals"]:
        achieved = get_goal_achieved(concept)
        assert len(achieved) > 20
        assert concept in CONCEPT_GOALS
        assert CONCEPT_GOALS[concept]["achieved"] == achieved


def test_dynamic_fallback_for_custom_concepts():
    """Verify graceful synthesis for concepts outside the predefined dictionary."""
    goal = get_learning_goal("binary_search_tree", topic="Data Structures")
    assert "Binary Search Tree" in goal
    assert "Data Structures" in goal

    achieved = get_goal_achieved("binary_search_tree")
    assert "Binary Search Tree" in achieved


# ── Unit Tests: Card Presentation ─────────────────────────────────────────────

def test_learning_state_card_initial_attempt():
    """First attempt must show Current approach and NOT show Previous approach."""
    f = io.StringIO()
    with redirect_stdout(f):
        print_learning_state_card(
            concept="call_stack",
            concept_display="Call Stack",
            mastery_pct=42,
            current_style="analogy",
            attempt=1,
            goal="Understand how function calls are added to the call stack.",
        )
    out = f.getvalue()

    assert "🎯 YOUR LEARNING STATE" in out
    assert "Call Stack" in out
    assert "42%" in out
    assert "Current approach: Analogy" in out
    assert "Current goal:" in out
    assert "Understand how function calls" in out
    assert "Previous approach" not in out
    assert "Result: Did not resolve" not in out


def test_learning_state_card_retry_attempt():
    """Retry attempt must show Previous approach ❌, failure result, next approach, reason, and goal."""
    f = io.StringIO()
    with redirect_stdout(f):
        print_learning_state_card(
            concept="call_stack",
            concept_display="Call Stack",
            mastery_pct=37,
            current_style="formal_pseudocode",
            attempt=2,
            prev_style="analogy",
            prev_failed=True,
            adaptation_reason="switching to untried style after analogy failed",
            goal="Understand how function calls are added to the call stack.",
        )
    out = f.getvalue()

    assert "🎯 YOUR LEARNING STATE" in out
    assert "Call Stack" in out
    assert "37%" in out
    assert "Previous approach: Analogy ❌" in out
    assert "Result: Did not resolve the gap" in out
    assert "Next approach: Formal Pseudocode" in out
    assert "Reason: switching to untried style after analogy failed" in out
    assert "Current goal:" in out
    assert "Understand how function calls" in out


def test_concept_improved_card():
    """Successful retest card must display old ➔ new mastery, delta, goal achieved, and next step."""
    f = io.StringIO()
    with redirect_stdout(f):
        print_concept_improved_card(
            concept_display="Call Stack",
            old_mastery=0.42,
            new_mastery=0.62,
            goal_achieved="You can now trace stack frame accumulation and return unwinding.",
            next_step="Continue to the next knowledge gap: Base Case",
        )
    out = f.getvalue()

    assert "✓ CONCEPT IMPROVED" in out
    assert "Call Stack" in out
    assert "42% ➔ 62%" in out
    assert "(+20%)" in out
    assert "Goal achieved:" in out
    assert "You can now trace stack frame accumulation" in out
    assert "Next ➔ Continue to the next knowledge gap: Base Case" in out


from unittest.mock import patch
from remediation.schema import ExplanationPayload


def test_drive_session_loop_renders_state_and_improvement(tmp_path):
    """Verify _drive_session_loop outputs learning state card and concept improved card."""
    store = Store(str(tmp_path / "test_goals.db"))
    s = _test_settings(llm_mode="real")
    flow = RemediationFlow()

    # Start session with ananya_analogy (fails Q5: call_stack)
    answers = dict(PERSONA_QUIZ_ANSWERS["ananya_analogy"])
    run_id = start_session(store, "test_student", answers, s)

    # Provider that answers correctly on first retest attempt
    def retest_provider(student_id, concept, style, attempt):
        return "b"  # correct for attempt 1

    def _fake_complete(*args, **kwargs):
        return ExplanationPayload(
            student_id="test_student",
            concept="call_stack",
            style="analogy",
            text="Call stack analogy explanation."
        )

    f = io.StringIO()
    with patch("slice.llm.complete", side_effect=_fake_complete):
        with redirect_stdout(f):
            _drive_session_loop(store, run_id, "test_student", s, flow, interactive=False, retest_provider=retest_provider)
    out = f.getvalue()

    # Verify initial learning state card was printed
    assert "🎯 YOUR LEARNING STATE" in out
    assert "Current approach:" in out
    assert "Current goal:" in out

    # Verify concept improved card was printed on pass with mastery delta
    assert "✓ CONCEPT IMPROVED" in out
    assert "Goal achieved:" in out
    assert "(+" in out
    assert "All concepts resolved! Session complete." in out


def test_drive_session_loop_retry_renders_previous_approach_and_next_goal(tmp_path):
    """Verify session loop on retry displays previous approach ❌, failure result, next approach, and goal."""
    store = Store(str(tmp_path / "test_goals_retry.db"))
    s = _test_settings(llm_mode="real")
    flow = RemediationFlow()

    # Start session with ananya_analogy (fails Q5: call_stack)
    answers = dict(PERSONA_QUIZ_ANSWERS["ananya_analogy"])
    run_id = start_session(store, "test_retry_student", answers, s)

    # Provider that fails attempt 1 ("a"), and passes attempt 2 ("b")
    def retest_provider(student_id, concept, style, attempt):
        if attempt == 1:
            return "a"  # wrong
        return "b"  # correct

    def _fake_complete(*args, **kwargs):
        step = kwargs.get("step", "")
        style = "formal_pseudocode" if "pseudocode" in step else "analogy"
        return ExplanationPayload(
            student_id="test_retry_student",
            concept="call_stack",
            style=style,
            text=f"Call stack {style} explanation."
        )

    f = io.StringIO()
    with patch("slice.llm.complete", side_effect=_fake_complete):
        with redirect_stdout(f):
            _drive_session_loop(store, run_id, "test_retry_student", s, flow, interactive=False, retest_provider=retest_provider)
    out = f.getvalue()

    # Verify attempt 1 initial state card
    assert "🎯 YOUR LEARNING STATE" in out
    assert "Current approach:" in out

    # Verify attempt 1 failure card and mistake feedback
    assert "FAILED ❌" in out
    assert "Why your answer was wrong:" in out

    # Verify attempt 2 retry learning state card
    assert "Previous approach:" in out
    assert "❌" in out
    assert "Result: Did not resolve the gap" in out
    assert "Next approach:" in out
    assert "Reason:" in out
    assert "Current goal:" in out

    # Verify attempt 2 pass improvement card
    assert "✓ CONCEPT IMPROVED" in out
    assert "Goal achieved:" in out
    assert "All concepts resolved! Session complete." in out
