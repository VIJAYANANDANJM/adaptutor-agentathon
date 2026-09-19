"""
Tests for slice/runner.py — State machine execution and backward-loop tests.
"""
import os
import pytest

os.environ.setdefault("LLM_MODE", "mock")

from slice.store import Store
from slice.runner import advance, Context
from slice.records import RunState
from slice.config import Settings
from remediation.flow import RemediationFlow, start_session, submit_retest


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


class TestRunner:
    def test_advance_reaches_terminal(self, store):
        """A run with all correct answers should reach COMPLETE."""
        s = _settings()
        correct_answers = {
            "Q1": "a", "Q2": "b", "Q3": "b", "Q4": "b",
            "Q5": "b", "Q6": "c", "Q7": "a", "Q8": "a",
        }
        run_id = start_session(store, "perfect_student", correct_answers, s)
        flow = RemediationFlow()
        state = advance(store, run_id, flow, s)
        assert state == RunState.COMPLETE

    def test_advance_with_no_handler(self, store):
        """A run in a state with no handler should fail."""
        s = _settings()

        class EmptyFlow:
            name = "empty"
            handlers = {}

        run_id = store.create_run("test")
        state = advance(store, run_id, EmptyFlow(), s)
        assert state == RunState.FAILED

    def test_max_steps_fence(self, store):
        """Runner should stop after max_steps to prevent infinite loops."""
        s = _settings()

        def loop_handler(ctx):
            # Return a different state to avoid no_progress detection
            current = store.get_state(ctx.run_id)
            if current == RunState.DRAFTING:
                return RunState.GATING
            return RunState.DRAFTING

        class LoopFlow:
            name = "loop"
            handlers = {
                RunState.DRAFTING: loop_handler,
                RunState.GATING: loop_handler,
            }

        run_id = store.create_run("test")
        state = advance(store, run_id, LoopFlow(), s, max_steps=5)
        assert state == RunState.FAILED

    def test_suspended_state_stops_advance(self, store):
        """Runner should stop when hitting AWAITING_EXPERT."""
        s = _settings()
        run_id = store.create_run("test")
        store.set_state(run_id, RunState.AWAITING_EXPERT)

        class NoopFlow:
            name = "noop"
            handlers = {}

        state = advance(store, run_id, NoopFlow(), s)
        assert state == RunState.AWAITING_EXPERT
