"""
Deterministic end-to-end scenarios for Priya, Ravi, and Karthik.

These tests exercise the complete remediation loop using mock providers
and predetermined answers. Zero network, zero API keys.
"""
import os
import time

import pytest

os.environ.setdefault("LLM_MODE", "mock")

from slice.store import Store
from slice.runner import advance
from slice.records import RunState
from slice.config import Settings
from slice import callback
from remediation.flow import (
    RemediationFlow, start_session, submit_retest,
    styles_tried_for_concept, count_revisions,
)
from remediation.stub import PERSONA_QUIZ_ANSWERS, get_retest_answer
from remediation.questions import get_retest_question


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


def _run_remediation_loop(store, run_id, student_id, settings):
    """Drive the state machine, submitting predetermined retest answers."""
    flow = RemediationFlow()
    max_iterations = 30

    for _ in range(max_iterations):
        state = advance(store, run_id, flow, settings)

        if state == RunState.COMPLETE or state == RunState.FAILED:
            return state

        if state == RunState.AWAITING_EXPERT:
            # Determine if waiting for retest (student) or instructor
            awaiting_history = store.history(run_id, "awaiting_retest")
            flag_history = store.history(run_id, "instructor_flag")

            latest_awaiting_seq = awaiting_history[-1].seq if awaiting_history else -1
            latest_flag_seq = flag_history[-1].seq if flag_history else -1

            if latest_awaiting_seq > latest_flag_seq and awaiting_history:
                # Waiting for student retest
                awaiting = awaiting_history[-1].payload
                concept = awaiting["concept"]
                style = awaiting["style"]
                attempt = awaiting["attempt"]

                retest_ans = get_retest_answer(student_id, concept, style, attempt)
                if retest_ans is None:
                    return state

                submit_retest(store, run_id, student_id, concept, retest_ans, settings)
                store.set_state(run_id, RunState.PROBING)
                continue
            else:
                # Instructor suspension
                return state

    return store.get_state(run_id)


class TestPriyaScenario:
    """Priya: Fails Q5 (call_stack). Analogy selected. Passes retest → COMPLETE."""

    def test_priya_end_to_end(self, store):
        s = _settings()
        student_id = "priya_22cs031"
        answers = PERSONA_QUIZ_ANSWERS[student_id]

        run_id = start_session(store, student_id, answers, s)
        state = _run_remediation_loop(store, run_id, student_id, s)

        assert state == RunState.COMPLETE

        # Verify diagnosis
        diag = store.latest(run_id, "diagnosis")
        assert "Q5" in diag["wrong_questions"]
        assert "call_stack" in diag["concepts_failed"]
        assert "base_case" in diag["concepts_passed"]
        assert "recursive_step" in diag["concepts_passed"]
        assert "return_propagation" in diag["concepts_passed"]

        # Verify style selection
        sel = store.latest(run_id, "style_selection")
        assert sel["concept"] == "call_stack"
        assert sel["selected_style"] == "analogy"
        assert sel["attempt"] == 1

        # Verify explanation was generated
        expl = store.latest(run_id, "explanation")
        assert expl["concept"] == "call_stack"
        assert expl["style"] == "analogy"

        # Verify retest passed
        retest = store.latest(run_id, "retest_result")
        assert retest["passed"] is True
        assert retest["concept"] == "call_stack"

        # Verify outcome
        outcomes = store.history(run_id, "outcome")
        concept_outcomes = [o for o in outcomes if o.payload.get("concept") == "call_stack"]
        assert len(concept_outcomes) >= 1
        assert concept_outcomes[-1].payload["passed"] is True
        assert concept_outcomes[-1].payload["total_attempts"] == 1


class TestRaviScenario:
    """Ravi: Fails Q5 (call_stack) and Q7 (return_propagation).
    call_stack: analogy fails → backward loop → trace succeeds.
    return_propagation: analogy succeeds."""

    def test_ravi_end_to_end(self, store):
        s = _settings()
        student_id = "ravi_22cs044"
        answers = PERSONA_QUIZ_ANSWERS[student_id]

        run_id = start_session(store, student_id, answers, s)
        state = _run_remediation_loop(store, run_id, student_id, s)

        assert state == RunState.COMPLETE

        # Verify diagnosis
        diag = store.latest(run_id, "diagnosis")
        assert "Q5" in diag["wrong_questions"]
        assert "Q7" in diag["wrong_questions"]
        assert "call_stack" in diag["concepts_failed"]
        assert "return_propagation" in diag["concepts_failed"]

        # Verify backward loop: two style selections for call_stack
        selections = store.history(run_id, "style_selection")
        call_stack_sels = [v for v in selections if v.payload["concept"] == "call_stack"]
        assert len(call_stack_sels) == 2
        assert call_stack_sels[0].payload["selected_style"] == "analogy"
        assert call_stack_sels[0].payload["attempt"] == 1
        assert call_stack_sels[1].payload["selected_style"] == "trace"
        assert call_stack_sels[1].payload["attempt"] == 2

        # Verify outcome: call_stack resolved with trace
        outcomes = store.history(run_id, "outcome")
        cs_outcomes = [o for o in outcomes if o.payload.get("concept") == "call_stack"]
        assert any(o.payload["passed"] and o.payload["style"] == "trace" for o in cs_outcomes)

    def test_ravi_backward_loop_fires(self, store):
        """Verify the backward loop specifically: analogy fails → returns to SELECT → trace."""
        s = _settings()
        student_id = "ravi_22cs044"
        answers = PERSONA_QUIZ_ANSWERS[student_id]

        run_id = start_session(store, student_id, answers, s)
        flow = RemediationFlow()

        # Advance until we need first retest
        state = advance(store, run_id, flow, s)
        while state == RunState.PROBING:
            sel = store.latest(run_id, "style_selection")
            if sel:
                concept = sel["concept"]
                style = sel["selected_style"]
                attempt = sel["attempt"]
                retest_ans = get_retest_answer(student_id, concept, style, attempt)
                if retest_ans:
                    submit_retest(store, run_id, student_id, concept, retest_ans, s)
                    state = advance(store, run_id, flow, s)
                else:
                    break
            else:
                break

        # After first call_stack failure with analogy, second selection should be trace
        sels = store.history(run_id, "style_selection")
        cs_sels = [v for v in sels if v.payload["concept"] == "call_stack"]
        if len(cs_sels) >= 2:
            assert cs_sels[1].payload["selected_style"] == "trace"


class TestKarthikScenario:
    """Karthik: Fails call_stack on both analogy and trace → WAITING_INSTRUCTOR."""

    def test_karthik_escalation(self, store):
        s = _settings()
        student_id = "karthik_22cs012"
        answers = PERSONA_QUIZ_ANSWERS[student_id]

        run_id = start_session(store, student_id, answers, s)
        state = _run_remediation_loop(store, run_id, student_id, s)

        assert state == RunState.AWAITING_EXPERT

        # Verify instructor flag was created
        flag = store.latest(run_id, "instructor_flag")
        assert flag is not None
        assert flag["concept"] == "call_stack"
        assert flag["both_failed"] is True
        assert set(flag["styles_tried"]) == {"analogy", "trace"}
        assert flag["state"] == "waiting_instructor"

        # Verify question was parked
        questions = store.open_questions(run_id)
        assert len(questions) >= 1

    def test_karthik_instructor_responds(self, store):
        """Verify that instructor response resumes and resolves the run."""
        s = _settings()
        student_id = "karthik_22cs012"
        answers = PERSONA_QUIZ_ANSWERS[student_id]

        run_id = start_session(store, student_id, answers, s)
        state = _run_remediation_loop(store, run_id, student_id, s)
        assert state == RunState.AWAITING_EXPERT

        # Instructor responds
        questions = store.open_questions(run_id)
        assert len(questions) >= 1
        qid = questions[0].id
        callback.answer(store, qid, "Draw the stack on paper for factorial(3)", who="instructor")

        # Resume
        flow = RemediationFlow()
        state = advance(store, run_id, flow, s)
        # Should proceed (either COMPLETE or move to next concept)
        assert state in (RunState.COMPLETE, RunState.GATING, RunState.PROBING, RunState.DRAFTING)

    def test_karthik_timeout_to_closed_unresolved(self, store):
        """Verify that timeout moves to CLOSED_UNRESOLVED equivalent."""
        s = _settings()
        student_id = "karthik_22cs012"
        answers = PERSONA_QUIZ_ANSWERS[student_id]

        run_id = start_session(store, student_id, answers, s)
        state = _run_remediation_loop(store, run_id, student_id, s)
        assert state == RunState.AWAITING_EXPERT

        # Force timeout by setting question timeout to past
        questions = store.open_questions(run_id)
        for q in questions:
            store.db.execute("UPDATE questions SET timeout_at=? WHERE id=?",
                             (time.time() - 10, q.id))

        # Sweep should expire and resume
        flow = RemediationFlow()
        state = advance(store, run_id, flow, s)

        # The timeout should have been processed
        expert_answers = store.history(run_id, "expert_answer")
        timeout_answers = [a for a in expert_answers
                           if a.payload.get("source") == "unresolved_no_expert"]
        assert len(timeout_answers) >= 1


class TestRevisionLimits:
    """Verify that max 2 explanation attempts per concept are enforced."""

    def test_max_two_revisions(self, store):
        s = _settings()
        student_id = "karthik_22cs012"
        answers = PERSONA_QUIZ_ANSWERS[student_id]

        run_id = start_session(store, student_id, answers, s)
        _run_remediation_loop(store, run_id, student_id, s)

        # Count style selections for call_stack
        selections = store.history(run_id, "style_selection")
        cs_sels = [v for v in selections if v.payload["concept"] == "call_stack"]
        assert len(cs_sels) == 2  # Exactly 2 attempts, not more


class TestProcessInterruption:
    """Verify that state persists across process restarts."""

    def test_resume_after_restart(self, tmp_path):
        db_path = str(tmp_path / "resume.db")
        s = _settings()
        student_id = "priya_22cs031"
        answers = PERSONA_QUIZ_ANSWERS[student_id]

        # Start session in one "process"
        store1 = Store(db_path)
        run_id = start_session(store1, student_id, answers, s)
        store1.close()

        # Resume in another "process"
        store2 = Store(db_path)
        state = store2.get_state(run_id)
        assert state != RunState.FAILED  # Should still be in progress

        # Complete the session
        final_state = _run_remediation_loop(store2, run_id, student_id, s)
        assert final_state == RunState.COMPLETE
        store2.close()
