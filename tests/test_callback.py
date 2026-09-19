"""
Tests for slice/callback.py — Instructor suspension, timeout, and resume tests.
"""
import os
import time

import pytest

os.environ.setdefault("LLM_MODE", "mock")

from slice.store import Store
from slice.records import RunState
from slice import callback
from slice.config import Settings


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


class TestCallback:
    def test_ask_suspends_run(self, store):
        run_id = store.create_run("test")
        s = _settings()
        qid = callback.ask(store, run_id, "Need help with call_stack",
                           {"student_id": "karthik", "concept": "call_stack",
                            "resume_state": RunState.PROBING.value}, s)
        assert store.get_state(run_id) == RunState.AWAITING_EXPERT
        q = store.get_question(qid)
        assert q is not None
        assert not q.is_answered

    def test_answer_resumes_run(self, store):
        run_id = store.create_run("test")
        s = _settings()
        qid = callback.ask(store, run_id, "Need help",
                           {"resume_state": RunState.PROBING.value}, s)
        assert store.get_state(run_id) == RunState.AWAITING_EXPERT

        result_run = callback.answer(store, qid, "Here is a hint", who="instructor")
        assert result_run == run_id
        assert store.get_state(run_id) == RunState.PROBING
        q = store.get_question(qid)
        assert q.is_answered
        assert q.answer == "Here is a hint"

    def test_answer_is_write_once(self, store):
        run_id = store.create_run("test")
        s = _settings()
        qid = callback.ask(store, run_id, "Q?",
                           {"resume_state": RunState.PROBING.value}, s)
        callback.answer(store, qid, "First answer")
        callback.answer(store, qid, "Second answer")  # should be ignored
        q = store.get_question(qid)
        assert q.answer == "First answer"

    def test_sweep_expires_old_questions(self, store):
        run_id = store.create_run("test")
        # Create a question with timeout in the past
        qid = store.ask(run_id, "Test?", {"resume_state": RunState.PROBING.value}, 0)
        # Manually set timeout to past
        store.db.execute("UPDATE questions SET timeout_at=? WHERE id=?",
                         (time.time() - 10, qid))
        store.set_state(run_id, RunState.AWAITING_EXPERT)

        expired = callback.sweep(store, run_id)
        assert len(expired) == 1
        assert expired[0].id == qid
        # Run should be resumed
        assert store.get_state(run_id) == RunState.PROBING

    def test_pending_excludes_expired(self, store):
        run_id = store.create_run("test")
        qid = store.ask(run_id, "Test?", {}, 0)
        store.db.execute("UPDATE questions SET timeout_at=? WHERE id=?",
                         (time.time() - 10, qid))
        pending = callback.pending(store, run_id)
        assert len(pending) == 0

    def test_answer_nonexistent_question(self, store):
        result = callback.answer(store, "nonexistent_q", "answer")
        assert result is None

    def test_callback_persists_across_restart(self, tmp_path):
        """Verify that suspended state and questions survive process restart."""
        db_path = str(tmp_path / "callback.db")
        s = _settings()

        s1 = Store(db_path)
        run_id = s1.create_run("test")
        qid = callback.ask(s1, run_id, "Instructor help needed",
                           {"resume_state": RunState.PROBING.value}, s)
        s1.close()

        # Simulate process restart
        s2 = Store(db_path)
        assert s2.get_state(run_id) == RunState.AWAITING_EXPERT
        q = s2.get_question(qid)
        assert q is not None
        assert not q.is_answered

        callback.answer(s2, qid, "Instructor responded")
        assert s2.get_state(run_id) == RunState.PROBING
        s2.close()
