"""
Tests for slice/store.py — Persistence and append-only trigger tests.
"""
import os
import sqlite3
import tempfile

import pytest

from slice.store import Store
from slice.records import RunState


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test.db"
    s = Store(str(db_path))
    yield s
    s.close()


class TestStore:
    def test_create_run(self, store):
        run_id = store.create_run("test_domain")
        assert run_id.startswith("run_")
        state = store.get_state(run_id)
        assert state == RunState.DRAFTING

    def test_set_and_get_state(self, store):
        run_id = store.create_run("test")
        store.set_state(run_id, RunState.GATING)
        assert store.get_state(run_id) == RunState.GATING

    def test_append_and_latest(self, store):
        run_id = store.create_run("test")
        store.append(run_id, "diagnosis", {"concepts_failed": ["call_stack"]}, "system")
        latest = store.latest(run_id, "diagnosis")
        assert latest is not None
        assert latest["concepts_failed"] == ["call_stack"]

    def test_append_only_no_update(self, store):
        run_id = store.create_run("test")
        store.append(run_id, "thesis", {"v": 1}, "agent")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store.db.execute(
                "UPDATE versions SET payload_json='{}' WHERE run_id=? AND seq=1",
                (run_id,)
            )

    def test_append_only_no_delete(self, store):
        run_id = store.create_run("test")
        store.append(run_id, "thesis", {"v": 1}, "agent")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store.db.execute(
                "DELETE FROM versions WHERE run_id=? AND seq=1",
                (run_id,)
            )

    def test_history_returns_ordered_versions(self, store):
        run_id = store.create_run("test")
        store.append(run_id, "step", {"n": 1}, "a")
        store.append(run_id, "step", {"n": 2}, "a")
        store.append(run_id, "step", {"n": 3}, "a")
        h = store.history(run_id, "step")
        assert len(h) == 3
        assert [v.payload["n"] for v in h] == [1, 2, 3]

    def test_replay(self, store):
        run_id = store.create_run("test")
        store.append(run_id, "a", {"x": 1}, "p")
        store.append(run_id, "b", {"x": 2}, "p")
        r = store.replay(run_id)
        assert len(r) == 2
        assert r[0].kind == "a"
        assert r[1].kind == "b"

    def test_meta(self, store):
        run_id = store.create_run("test", meta={"student_id": "priya_22cs031"})
        m = store.meta(run_id)
        assert m["student_id"] == "priya_22cs031"

    def test_counters(self, store):
        run_id = store.create_run("test")
        assert store.counter(run_id, "tokens") == 0.0
        store.bump(run_id, "tokens", 100)
        assert store.counter(run_id, "tokens") == 100.0
        store.bump(run_id, "tokens", 50)
        assert store.counter(run_id, "tokens") == 150.0
        store.reset_counter(run_id, "tokens")
        assert store.counter(run_id, "tokens") == 0.0

    def test_persistence_across_connections(self, tmp_path):
        db_path = str(tmp_path / "persist.db")
        s1 = Store(db_path)
        run_id = s1.create_run("test")
        s1.append(run_id, "data", {"key": "value"}, "agent")
        s1.close()

        s2 = Store(db_path)
        latest = s2.latest(run_id, "data")
        assert latest is not None
        assert latest["key"] == "value"
        s2.close()

    def test_all_versions_by_kind(self, store):
        r1 = store.create_run("test")
        r2 = store.create_run("test")
        store.append(r1, "outcome", {"concept": "call_stack", "passed": True}, "sys")
        store.append(r2, "outcome", {"concept": "call_stack", "passed": False}, "sys")
        results = store.all_versions_by_kind("outcome")
        assert len(results) == 2

    def test_list_runs(self, store):
        store.create_run("d1")
        store.create_run("d2")
        runs = store.list_runs()
        assert len(runs) == 2

    def test_get_state_nonexistent(self, store):
        with pytest.raises(KeyError):
            store.get_state("nonexistent_run")
