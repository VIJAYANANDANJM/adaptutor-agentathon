"""
Persistent Learner Model.

Tracks per-student, per-concept mastery and intervention history.
All state lives in SQLite via the Store — survives process restarts,
distinct runs, and session boundaries.

Mastery update rules:
    Initial quiz correct   = 85%
    Initial quiz incorrect = 25%
    Retest pass            = +45% (capped at 95%)
    Retest fail            = -15% (floored at 10%)
    Instructor resolved    = +50% (capped at 95%)
"""
from __future__ import annotations

from typing import Any

from slice.store import Store


# ── Mastery constants ──────────────────────────────────────────────────────

MASTERY_QUIZ_CORRECT = 0.85
MASTERY_QUIZ_INCORRECT = 0.25
MASTERY_RETEST_PASS_DELTA = 0.45
MASTERY_RETEST_PASS_CAP = 0.95
MASTERY_RETEST_FAIL_DELTA = -0.15
MASTERY_RETEST_FAIL_FLOOR = 0.10
MASTERY_INSTRUCTOR_DELTA = 0.50
MASTERY_INSTRUCTOR_CAP = 0.95

WEAK_THRESHOLD = 0.60
STRONG_THRESHOLD = 0.75


class LearnerModel:
    """Facade over Store's learner tables. One instance per session."""

    def __init__(self, store: Store, student_id: str):
        self.store = store
        self.student_id = student_id

    # ── Profile queries ────────────────────────────────────────────────

    @property
    def profile(self) -> dict[str, Any]:
        """Full learner profile from the database."""
        return self.store.get_learner_profile(self.student_id)

    @property
    def mastery(self) -> dict[str, float]:
        return self.profile["mastery"]

    @property
    def weak_concepts(self) -> list[str]:
        return [c for c, m in self.mastery.items() if m < WEAK_THRESHOLD]

    @property
    def strong_concepts(self) -> list[str]:
        return [c for c, m in self.mastery.items() if m >= STRONG_THRESHOLD]

    @property
    def style_efficacy(self) -> dict[str, dict[str, Any]]:
        return self.store.get_style_efficacy(self.student_id)

    @property
    def intervention_history(self) -> list[dict[str, Any]]:
        return self.store.get_intervention_history(self.student_id)

    def concept_mastery(self, concept: str) -> float:
        """Current mastery for a concept. Returns 0.0 if no record."""
        m = self.store.get_mastery(self.student_id, concept)
        return m if m is not None else 0.0

    def overall_mastery(self) -> float:
        """Average mastery across all tracked concepts."""
        m = self.mastery
        if not m:
            return 0.0
        return sum(m.values()) / len(m)

    # ── Mastery updates ────────────────────────────────────────────────

    def init_from_quiz(self, concepts_passed: list[str],
                       concepts_failed: list[str]) -> None:
        """Set baseline mastery from initial quiz results."""
        for c in concepts_passed:
            self.store.upsert_mastery(self.student_id, c, MASTERY_QUIZ_CORRECT)
        for c in concepts_failed:
            # Only set baseline if no existing mastery (don't overwrite prior data)
            existing = self.store.get_mastery(self.student_id, c)
            if existing is None:
                self.store.upsert_mastery(self.student_id, c, MASTERY_QUIZ_INCORRECT)
            # If student had prior mastery, leave it — they regressed, set to quiz baseline
            else:
                self.store.upsert_mastery(self.student_id, c, MASTERY_QUIZ_INCORRECT)

    def update_on_retest(self, concept: str, style: str, attempt: int,
                         passed: bool) -> tuple[float, float]:
        """Update mastery after a retest. Returns (old_mastery, new_mastery)."""
        old = self.concept_mastery(concept)
        if passed:
            new = min(old + MASTERY_RETEST_PASS_DELTA, MASTERY_RETEST_PASS_CAP)
        else:
            new = max(old + MASTERY_RETEST_FAIL_DELTA, MASTERY_RETEST_FAIL_FLOOR)
        self.store.upsert_mastery(self.student_id, concept, new)
        self.store.record_intervention(self.student_id, concept, style, attempt, passed)
        return old, new

    def update_on_instructor(self, concept: str) -> tuple[float, float]:
        """Update mastery after instructor intervention resolves the concept."""
        old = self.concept_mastery(concept)
        new = min(old + MASTERY_INSTRUCTOR_DELTA, MASTERY_INSTRUCTOR_CAP)
        self.store.upsert_mastery(self.student_id, concept, new)
        self.store.record_intervention(self.student_id, concept, "instructor", 0, True)
        return old, new

    def style_history_for_display(self) -> dict[str, str]:
        """Formatted style efficacy for UI cards, e.g. 'Analogy: 2/3 (67%)'."""
        eff = self.style_efficacy
        result = {}
        for style, data in eff.items():
            pct = int(data["rate"] * 100)
            result[style] = f"{data['wins']}/{data['total']} passed ({pct}%)"
        return result
