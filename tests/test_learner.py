"""
Tests for remediation/learner.py — Persistent Learner Model.

Covers: mastery initialization from quiz, retest updates (pass/fail),
instructor intervention, weak/strong classification, style efficacy,
and persistence across Store restarts.
"""
import os
import pytest

os.environ.setdefault("LLM_MODE", "mock")

from slice.store import Store
from remediation.learner import (
    LearnerModel,
    MASTERY_QUIZ_CORRECT, MASTERY_QUIZ_INCORRECT,
    MASTERY_RETEST_PASS_DELTA, MASTERY_RETEST_PASS_CAP,
    MASTERY_RETEST_FAIL_DELTA, MASTERY_RETEST_FAIL_FLOOR,
    MASTERY_INSTRUCTOR_DELTA, MASTERY_INSTRUCTOR_CAP,
    WEAK_THRESHOLD, STRONG_THRESHOLD,
)


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


class TestMasteryInitFromQuiz:
    """Mastery initialization: correct = 85%, incorrect = 25%."""

    def test_quiz_correct_sets_85(self, store):
        lm = LearnerModel(store, "stu1")
        lm.init_from_quiz(["base_case"], [])
        assert lm.concept_mastery("base_case") == pytest.approx(MASTERY_QUIZ_CORRECT)

    def test_quiz_incorrect_sets_25(self, store):
        lm = LearnerModel(store, "stu1")
        lm.init_from_quiz([], ["call_stack"])
        assert lm.concept_mastery("call_stack") == pytest.approx(MASTERY_QUIZ_INCORRECT)

    def test_quiz_mixed(self, store):
        lm = LearnerModel(store, "stu1")
        lm.init_from_quiz(["base_case", "recursive_step"], ["call_stack"])
        assert lm.concept_mastery("base_case") == pytest.approx(0.85)
        assert lm.concept_mastery("recursive_step") == pytest.approx(0.85)
        assert lm.concept_mastery("call_stack") == pytest.approx(0.25)

    def test_untracked_concept_returns_zero(self, store):
        lm = LearnerModel(store, "stu1")
        assert lm.concept_mastery("nonexistent") == 0.0


class TestMasteryRetestUpdates:
    """Retest pass = +45% (cap 95%), fail = -15% (floor 10%)."""

    def test_retest_pass_adds_45(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.25)
        old, new = lm.update_on_retest("call_stack", "analogy", 1, True)
        assert old == pytest.approx(0.25)
        assert new == pytest.approx(0.70)

    def test_retest_pass_capped_at_95(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.80)
        old, new = lm.update_on_retest("call_stack", "trace", 1, True)
        assert new == pytest.approx(MASTERY_RETEST_PASS_CAP)

    def test_retest_fail_subtracts_15(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.50)
        old, new = lm.update_on_retest("call_stack", "analogy", 1, False)
        assert old == pytest.approx(0.50)
        assert new == pytest.approx(0.35)

    def test_retest_fail_floored_at_10(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.15)
        old, new = lm.update_on_retest("call_stack", "analogy", 1, False)
        assert new == pytest.approx(MASTERY_RETEST_FAIL_FLOOR)

    def test_sequential_updates(self, store):
        """Quiz incorrect (25%) → fail retest (10%) → pass retest (55%)."""
        lm = LearnerModel(store, "stu1")
        lm.init_from_quiz([], ["call_stack"])
        assert lm.concept_mastery("call_stack") == pytest.approx(0.25)

        lm.update_on_retest("call_stack", "analogy", 1, False)
        assert lm.concept_mastery("call_stack") == pytest.approx(0.10)

        lm.update_on_retest("call_stack", "trace", 2, True)
        assert lm.concept_mastery("call_stack") == pytest.approx(0.55)


class TestMasteryInstructorUpdate:
    """Instructor resolution = +50% (cap 95%)."""

    def test_instructor_adds_50(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.10)
        old, new = lm.update_on_instructor("call_stack")
        assert old == pytest.approx(0.10)
        assert new == pytest.approx(0.60)

    def test_instructor_capped_at_95(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.80)
        old, new = lm.update_on_instructor("call_stack")
        assert new == pytest.approx(MASTERY_INSTRUCTOR_CAP)


class TestWeakStrongClassification:
    """Weak < 60%, Strong >= 75%."""

    def test_weak_concepts(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.25)
        store.upsert_mastery("stu1", "base_case", 0.85)
        assert "call_stack" in lm.weak_concepts
        assert "base_case" not in lm.weak_concepts

    def test_strong_concepts(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.85)
        store.upsert_mastery("stu1", "base_case", 0.50)
        assert "call_stack" in lm.strong_concepts
        assert "base_case" not in lm.strong_concepts

    def test_middle_zone(self, store):
        """60% <= mastery < 75% is neither weak nor strong."""
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "call_stack", 0.65)
        assert "call_stack" not in lm.weak_concepts
        assert "call_stack" not in lm.strong_concepts


class TestStyleWinRate:
    """Style efficacy: wins/total per style."""

    def test_single_style(self, store):
        lm = LearnerModel(store, "stu1")
        store.record_intervention("stu1", "call_stack", "analogy", 1, True)
        store.record_intervention("stu1", "base_case", "analogy", 1, True)
        eff = lm.style_efficacy
        assert eff["analogy"]["wins"] == 2
        assert eff["analogy"]["total"] == 2
        assert eff["analogy"]["rate"] == pytest.approx(1.0)

    def test_mixed_results(self, store):
        lm = LearnerModel(store, "stu1")
        store.record_intervention("stu1", "call_stack", "trace", 1, True)
        store.record_intervention("stu1", "base_case", "trace", 1, False)
        eff = lm.style_efficacy
        assert eff["trace"]["wins"] == 1
        assert eff["trace"]["total"] == 2
        assert eff["trace"]["rate"] == pytest.approx(0.5)

    def test_display_format(self, store):
        lm = LearnerModel(store, "stu1")
        store.record_intervention("stu1", "call_stack", "analogy", 1, True)
        store.record_intervention("stu1", "call_stack", "analogy", 2, False)
        display = lm.style_history_for_display()
        assert "analogy" in display
        assert "1/2" in display["analogy"]
        assert "50%" in display["analogy"]


class TestInterventionHistory:
    """Intervention history tracking."""

    def test_records_interventions(self, store):
        lm = LearnerModel(store, "stu1")
        lm.update_on_retest("call_stack", "analogy", 1, False)
        lm.update_on_retest("call_stack", "trace", 2, True)
        history = lm.intervention_history
        assert len(history) == 2
        assert history[0]["concept"] == "call_stack"
        assert history[0]["style"] == "analogy"
        assert history[0]["passed"] is False
        assert history[1]["style"] == "trace"
        assert history[1]["passed"] is True

    def test_instructor_records_intervention(self, store):
        lm = LearnerModel(store, "stu1")
        lm.update_on_instructor("call_stack")
        history = lm.intervention_history
        assert len(history) == 1
        assert history[0]["style"] == "instructor"
        assert history[0]["passed"] is True


class TestPersistenceAcrossRestarts:
    """Learner model persists across Store restarts."""

    def test_mastery_persists(self, tmp_path):
        db_path = str(tmp_path / "persist.db")

        s1 = Store(db_path)
        lm1 = LearnerModel(s1, "stu1")
        lm1.init_from_quiz(["base_case"], ["call_stack"])
        lm1.update_on_retest("call_stack", "analogy", 1, True)
        s1.close()

        s2 = Store(db_path)
        lm2 = LearnerModel(s2, "stu1")
        assert lm2.concept_mastery("base_case") == pytest.approx(0.85)
        assert lm2.concept_mastery("call_stack") == pytest.approx(0.70)  # 0.25 + 0.45
        s2.close()

    def test_intervention_history_persists(self, tmp_path):
        db_path = str(tmp_path / "persist.db")

        s1 = Store(db_path)
        lm1 = LearnerModel(s1, "stu1")
        lm1.update_on_retest("call_stack", "analogy", 1, False)
        s1.close()

        s2 = Store(db_path)
        lm2 = LearnerModel(s2, "stu1")
        history = lm2.intervention_history
        assert len(history) == 1
        assert history[0]["style"] == "analogy"
        assert history[0]["passed"] is False
        s2.close()

    def test_style_efficacy_persists(self, tmp_path):
        db_path = str(tmp_path / "persist.db")

        s1 = Store(db_path)
        s1.record_intervention("stu1", "call_stack", "analogy", 1, True)
        s1.record_intervention("stu1", "call_stack", "analogy", 2, True)
        s1.close()

        s2 = Store(db_path)
        lm2 = LearnerModel(s2, "stu1")
        eff = lm2.style_efficacy
        assert eff["analogy"]["rate"] == pytest.approx(1.0)
        s2.close()


class TestOverallMastery:
    """Overall mastery average."""

    def test_average(self, store):
        lm = LearnerModel(store, "stu1")
        store.upsert_mastery("stu1", "base_case", 0.80)
        store.upsert_mastery("stu1", "call_stack", 0.40)
        assert lm.overall_mastery() == pytest.approx(0.60)

    def test_empty_mastery(self, store):
        lm = LearnerModel(store, "stu1")
        assert lm.overall_mastery() == 0.0
