"""
Tests for slice/budget.py — Budget fence and revision limit tests.
"""
import os
import pytest

os.environ.setdefault("LLM_MODE", "real")

from slice.store import Store
from slice.budget import Budget, BudgetExceeded
from slice.config import Settings


def _settings(**overrides) -> Settings:
    defaults = dict(
        api_key="",
        model="test",
        fallback_model="",
        escalation_model="",
        max_tokens=100,
        max_tokens_per_run=1000,
        max_attempts_per_step=3,
        expert_timeout_minutes=45,
        llm_mode="real",
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


class TestBudget:
    def test_token_tracking(self, store):
        run_id = store.create_run("test")
        b = Budget(store, run_id, _settings())
        assert b.tokens_used() == 0
        b.record_tokens(500)
        assert b.tokens_used() == 500
        assert b.tokens_remaining() == 500

    def test_token_fence(self, store):
        run_id = store.create_run("test")
        s = _settings(max_tokens_per_run=100)
        b = Budget(store, run_id, s)
        b.record_tokens(100)
        with pytest.raises(BudgetExceeded, match="token"):
            b.check_tokens()

    def test_attempt_tracking(self, store):
        run_id = store.create_run("test")
        b = Budget(store, run_id, _settings())
        assert b.attempts("explain") == 0
        n = b.attempt("explain")
        assert n == 1
        assert b.attempts("explain") == 1

    def test_attempt_fence(self, store):
        run_id = store.create_run("test")
        s = _settings(max_attempts_per_step=2)
        b = Budget(store, run_id, s)
        b.attempt("step")
        b.attempt("step")
        with pytest.raises(BudgetExceeded, match="attempt"):
            b.attempt("step")

    def test_reset_attempts(self, store):
        run_id = store.create_run("test")
        b = Budget(store, run_id, _settings())
        b.attempt("step")
        b.attempt("step")
        b.reset_attempts("step")
        assert b.attempts("step") == 0

    def test_budget_survives_restart(self, tmp_path):
        """Budget counters persist in SQLite across connections."""
        db_path = str(tmp_path / "budget.db")
        s1 = Store(db_path)
        run_id = s1.create_run("test")
        b1 = Budget(s1, run_id, _settings())
        b1.record_tokens(750)
        b1.attempt("explain")
        s1.close()

        s2 = Store(db_path)
        b2 = Budget(s2, run_id, _settings())
        assert b2.tokens_used() == 750
        assert b2.attempts("explain") == 1
        s2.close()

    def test_summary(self, store):
        run_id = store.create_run("test")
        b = Budget(store, run_id, _settings(max_tokens_per_run=1000))
        b.record_tokens(300)
        summary = b.summary()
        assert summary["tokens_used"] == 300
        assert summary["tokens_limit"] == 1000
        assert summary["tokens_remaining"] == 700

    def test_model_call_budget_fence(self, store):
        """Test that max 10 model calls per session is enforceable."""
        run_id = store.create_run("test")
        s = _settings(max_attempts_per_step=10)
        b = Budget(store, run_id, s)
        for i in range(10):
            store.bump(run_id, "model_calls")
        count = store.counter(run_id, "model_calls")
        assert count == 10
