"""
The system of record.

The single most important idea in this kit: **the context window is a cache,
the database is the truth.** Every agent turn reads state from here, calls a
model, and writes a new version back. The conversation is derived and
disposable.

The table is append-only. There is no update, no delete - and that is enforced
by SQLite triggers rather than by convention, so a well-meaning refactor at
hour 30 cannot quietly break it. Append-only buys you four things for free:

  * replay      - re-read the run exactly as it happened
  * diffs       - thesis v1 -> v2 -> v3 is just three rows
  * resume      - the process can die; the run cannot
  * audit       - "why did it decide that" has an answer

Stdlib only. sqlite3 and json.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .records import Question, RunState, Version, new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    domain      TEXT NOT NULL,
    state       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    meta_json   TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS versions (
    run_id       TEXT NOT NULL REFERENCES runs(id),
    seq          INTEGER NOT NULL,
    kind         TEXT NOT NULL,
    produced_by  TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   REAL NOT NULL,
    PRIMARY KEY (run_id, seq)
);
CREATE INDEX IF NOT EXISTS versions_by_kind ON versions(run_id, kind, seq);

-- Counters survive a resume. Attempt counts and token spend live here, not in
-- a Python variable that dies with the process.
CREATE TABLE IF NOT EXISTS counters (
    run_id TEXT NOT NULL REFERENCES runs(id),
    name   TEXT NOT NULL,
    value  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, name)
);

CREATE TABLE IF NOT EXISTS questions (
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(id),
    question     TEXT NOT NULL,
    context_json TEXT NOT NULL DEFAULT '{}',
    asked_at     REAL NOT NULL,
    timeout_at   REAL NOT NULL,
    answered_at  REAL,
    answer       TEXT
);
CREATE INDEX IF NOT EXISTS questions_open ON questions(run_id, answered_at);

-- The append-only invariant, enforced by the database itself.
CREATE TRIGGER IF NOT EXISTS versions_no_update
BEFORE UPDATE ON versions
BEGIN SELECT RAISE(ABORT, 'versions is append-only: write a new version'); END;

CREATE TRIGGER IF NOT EXISTS versions_no_delete
BEFORE DELETE ON versions
BEGIN SELECT RAISE(ABORT, 'versions is append-only: history is not editable'); END;

-- Persistent learner profiles: per-student, per-concept mastery.
CREATE TABLE IF NOT EXISTS learner_profiles (
    student_id  TEXT NOT NULL,
    concept     TEXT NOT NULL,
    mastery     REAL NOT NULL DEFAULT 0.0,
    updated_at  REAL NOT NULL,
    PRIMARY KEY (student_id, concept)
);

-- Intervention history: every attempt for every student.
CREATE TABLE IF NOT EXISTS intervention_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    concept     TEXT NOT NULL,
    style       TEXT NOT NULL,
    attempt     INTEGER NOT NULL,
    passed      INTEGER NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ih_student ON intervention_history(student_id);
CREATE INDEX IF NOT EXISTS ih_concept ON intervention_history(concept);
"""


class Store:
    """Durable run state. One file. Commit it, ship it, replay it."""

    def __init__(self, path: str | Path = "run.db") -> None:
        self.path = str(path)
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    # ---------------------------------------------------------------- runs

    def create_run(self, domain: str, meta: dict[str, Any] | None = None) -> str:
        run_id, now = new_id("run"), time.time()
        self.db.execute(
            "INSERT INTO runs(id, domain, state, created_at, updated_at, meta_json)"
            " VALUES (?,?,?,?,?,?)",
            (run_id, domain, RunState.DRAFTING.value, now, now, json.dumps(meta or {})),
        )
        return run_id

    def get_state(self, run_id: str) -> RunState:
        row = self.db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"no such run: {run_id}")
        return RunState(row["state"])

    def set_state(self, run_id: str, state: RunState) -> None:
        self.db.execute(
            "UPDATE runs SET state=?, updated_at=? WHERE id=?",
            (state.value, time.time(), run_id),
        )

    def meta(self, run_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT meta_json FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"no such run: {run_id}")
        return json.loads(row["meta_json"])

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT id, domain, state, created_at, updated_at FROM runs"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ versions

    def append(self, run_id: str, kind: str, payload: dict[str, Any], produced_by: str) -> int:
        """Write a new version. Returns its seq. Never overwrites anything."""
        cur = self.db.execute(
            "INSERT INTO versions(run_id, seq, kind, produced_by, payload_json, created_at)"
            " VALUES (?, (SELECT COALESCE(MAX(seq),0)+1 FROM versions WHERE run_id=?), ?,?,?,?)",
            (run_id, run_id, kind, produced_by, json.dumps(payload), time.time()),
        )
        self.db.execute("UPDATE runs SET updated_at=? WHERE id=?", (time.time(), run_id))
        row = self.db.execute(
            "SELECT MAX(seq) AS s FROM versions WHERE run_id=?", (run_id,)
        ).fetchone()
        _ = cur
        return int(row["s"])

    def latest(self, run_id: str, kind: str) -> dict[str, Any] | None:
        """Current state of one kind of record - what an agent reads before acting."""
        row = self.db.execute(
            "SELECT payload_json FROM versions WHERE run_id=? AND kind=?"
            " ORDER BY seq DESC LIMIT 1",
            (run_id, kind),
        ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def history(self, run_id: str, kind: str) -> list[Version]:
        """Every version of one kind, oldest first. This is the diff a judge wants."""
        rows = self.db.execute(
            "SELECT seq, kind, produced_by, payload_json, created_at FROM versions"
            " WHERE run_id=? AND kind=? ORDER BY seq",
            (run_id, kind),
        ).fetchall()
        return [_to_version(r) for r in rows]

    def replay(self, run_id: str) -> list[Version]:
        """The whole run, in order. Backs the `replay` CLI command."""
        rows = self.db.execute(
            "SELECT seq, kind, produced_by, payload_json, created_at FROM versions"
            " WHERE run_id=? ORDER BY seq",
            (run_id,),
        ).fetchall()
        return [_to_version(r) for r in rows]

    def all_versions_by_kind(self, kind: str) -> list[Version]:
        """All versions of a given kind across ALL runs. Used for population-level queries."""
        rows = self.db.execute(
            "SELECT seq, kind, produced_by, payload_json, created_at FROM versions"
            " WHERE kind=? ORDER BY created_at",
            (kind,),
        ).fetchall()
        return [_to_version(r) for r in rows]

    # ------------------------------------------------------------ counters

    def bump(self, run_id: str, name: str, by: float = 1) -> float:
        self.db.execute(
            "INSERT INTO counters(run_id, name, value) VALUES (?,?,?)"
            " ON CONFLICT(run_id, name) DO UPDATE SET value = value + excluded.value",
            (run_id, name, by),
        )
        return self.counter(run_id, name)

    def counter(self, run_id: str, name: str) -> float:
        row = self.db.execute(
            "SELECT value FROM counters WHERE run_id=? AND name=?", (run_id, name)
        ).fetchone()
        return float(row["value"]) if row else 0.0

    def reset_counter(self, run_id: str, name: str) -> None:
        self.db.execute("DELETE FROM counters WHERE run_id=? AND name=?", (run_id, name))

    # ----------------------------------------------------------- questions

    def ask(self, run_id: str, question: str, context: dict[str, Any], timeout_minutes: int) -> str:
        qid, now = new_id("q"), time.time()
        self.db.execute(
            "INSERT INTO questions(id, run_id, question, context_json, asked_at, timeout_at)"
            " VALUES (?,?,?,?,?,?)",
            (qid, run_id, question, json.dumps(context), now, now + timeout_minutes * 60),
        )
        return qid

    def answer(self, question_id: str, answer: str) -> None:
        self.db.execute(
            "UPDATE questions SET answer=?, answered_at=? WHERE id=? AND answer IS NULL",
            (answer, time.time(), question_id),
        )

    def get_question(self, question_id: str) -> Question | None:
        row = self.db.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        return _to_question(row) if row else None

    def open_questions(self, run_id: str | None = None) -> list[Question]:
        sql = "SELECT * FROM questions WHERE answered_at IS NULL"
        args: tuple = ()
        if run_id:
            sql += " AND run_id=?"
            args = (run_id,)
        return [_to_question(r) for r in self.db.execute(sql + " ORDER BY asked_at", args)]

    def close(self) -> None:
        self.db.close()

    # ------------------------------------------------- learner profiles

    def upsert_mastery(self, student_id: str, concept: str, mastery: float) -> None:
        """Set mastery for a student/concept. Clamps to [0.0, 1.0]."""
        mastery = max(0.0, min(1.0, mastery))
        self.db.execute(
            "INSERT INTO learner_profiles(student_id, concept, mastery, updated_at)"
            " VALUES (?,?,?,?)"
            " ON CONFLICT(student_id, concept) DO UPDATE SET mastery=excluded.mastery,"
            " updated_at=excluded.updated_at",
            (student_id, concept, mastery, time.time()),
        )

    def get_mastery(self, student_id: str, concept: str) -> float | None:
        row = self.db.execute(
            "SELECT mastery FROM learner_profiles WHERE student_id=? AND concept=?",
            (student_id, concept),
        ).fetchone()
        return float(row["mastery"]) if row else None

    def get_learner_profile(self, student_id: str) -> dict[str, Any]:
        """Full learner profile: mastery map, weak/strong concepts, style efficacy."""
        rows = self.db.execute(
            "SELECT concept, mastery FROM learner_profiles WHERE student_id=?",
            (student_id,),
        ).fetchall()
        mastery = {r["concept"]: float(r["mastery"]) for r in rows}
        weak = [c for c, m in mastery.items() if m < 0.60]
        strong = [c for c, m in mastery.items() if m >= 0.75]
        return {
            "student_id": student_id,
            "mastery": mastery,
            "weak_concepts": weak,
            "strong_concepts": strong,
            "style_efficacy": self.get_style_efficacy(student_id),
            "intervention_history": self.get_intervention_history(student_id),
        }

    def get_all_student_ids(self) -> list[str]:
        """Return all distinct student IDs that have learner profiles."""
        rows = self.db.execute(
            "SELECT DISTINCT student_id FROM learner_profiles ORDER BY student_id"
        ).fetchall()
        return [r["student_id"] for r in rows]

    # ------------------------------------------ intervention history

    def record_intervention(self, student_id: str, concept: str, style: str,
                            attempt: int, passed: bool) -> None:
        self.db.execute(
            "INSERT INTO intervention_history(student_id, concept, style, attempt, passed, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (student_id, concept, style, attempt, 1 if passed else 0, time.time()),
        )

    def get_intervention_history(self, student_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT concept, style, attempt, passed, created_at FROM intervention_history"
            " WHERE student_id=? ORDER BY created_at",
            (student_id,),
        ).fetchall()
        return [
            {"concept": r["concept"], "style": r["style"], "attempt": int(r["attempt"]),
             "passed": bool(r["passed"]), "timestamp": float(r["created_at"])}
            for r in rows
        ]

    def get_style_efficacy(self, student_id: str) -> dict[str, dict[str, Any]]:
        """Per-style win rate for a student: {style: {wins, total, rate}}."""
        rows = self.db.execute(
            "SELECT style, SUM(passed) as wins, COUNT(*) as total"
            " FROM intervention_history WHERE student_id=?"
            " GROUP BY style",
            (student_id,),
        ).fetchall()
        result = {}
        for r in rows:
            total = int(r["total"])
            wins = int(r["wins"])
            result[r["style"]] = {
                "wins": wins, "total": total,
                "rate": wins / total if total > 0 else 0.0,
            }
        return result

    def get_student_style_rate(self, student_id: str, style: str) -> float | None:
        """Success rate for a specific style for a student. None if no history."""
        row = self.db.execute(
            "SELECT SUM(passed) as wins, COUNT(*) as total"
            " FROM intervention_history WHERE student_id=? AND style=?",
            (student_id, style),
        ).fetchone()
        if row is None or int(row["total"]) == 0:
            return None
        return int(row["wins"]) / int(row["total"])

    def get_cohort_style_rate(self, style: str) -> float | None:
        """Population-level success rate for a style. None if no history."""
        row = self.db.execute(
            "SELECT SUM(passed) as wins, COUNT(*) as total"
            " FROM intervention_history WHERE style=?",
            (style,),
        ).fetchone()
        if row is None or int(row["total"]) == 0:
            return None
        return int(row["wins"]) / int(row["total"])


def _to_version(r: sqlite3.Row) -> Version:
    return Version(
        seq=int(r["seq"]),
        kind=r["kind"],
        produced_by=r["produced_by"],
        payload=json.loads(r["payload_json"]),
        created_at=float(r["created_at"]),
    )


def _to_question(r: sqlite3.Row) -> Question:
    return Question(
        id=r["id"],
        run_id=r["run_id"],
        question=r["question"],
        context=json.loads(r["context_json"]),
        asked_at=float(r["asked_at"]),
        timeout_at=float(r["timeout_at"]),
        answered_at=float(r["answered_at"]) if r["answered_at"] is not None else None,
        answer=r["answer"],
    )
