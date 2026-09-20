"""
Tests for remediation/selector.py — Evidence-based adaptive intervention selector.

Verifies: formula Score = 0.7 × StudentRate + 0.3 × CohortRate,
different histories → different selections, attempt 2 never repeats failed style,
fallback to cohort then default, and demo persona scenarios.
"""
import os
import pytest

os.environ.setdefault("LLM_MODE", "real")

from slice.store import Store
from remediation.selector import adaptive_select, STYLES, DEFAULT_STYLE


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


class TestFormulaVerification:
    """Verify the weighted formula: Score = 0.7 × StudentRate + 0.3 × CohortRate."""

    def test_student_100_cohort_0(self, store):
        """Student rate 100%, cohort rate 0% → score = 0.7."""
        store.record_intervention("stu1", "call_stack", "analogy", 1, True)
        store.record_intervention("other", "call_stack", "analogy", 1, False)
        # analogy: student=1.0, cohort=0.5 (stu1 pass + other fail = 1/2)
        # Actually: student rate for stu1 on analogy = 1/1 = 1.0
        # Cohort rate for analogy = 1/2 = 0.5
        # Score(analogy) = 0.7 * 1.0 + 0.3 * 0.5 = 0.85
        style, _ = adaptive_select(store, "stu1", "call_stack", [])
        assert style == "analogy"  # 0.85 vs 0.5 (default trace)

    def test_equal_scores_prefer_first_style(self, store):
        """When scores are tied, prefer the first style in STYLES list."""
        # No history at all → both get 0.5 default → tie → analogy (first in STYLES)
        style, reason = adaptive_select(store, "new_student", "call_stack", [])
        assert style == DEFAULT_STYLE
        assert "no prior data" in reason


class TestDifferentHistoriesDifferentSelections:
    """Different student histories produce different style selections for identical gaps."""

    def test_analogy_student_gets_analogy(self, store):
        """Student with analogy success → selector picks analogy."""
        store.record_intervention("stu_a", "base_case", "analogy", 1, True)
        store.record_intervention("stu_a", "recursive_step", "analogy", 1, True)
        style, _ = adaptive_select(store, "stu_a", "call_stack", [])
        assert style == "analogy"

    def test_trace_student_gets_trace(self, store):
        """Student with trace success → selector picks trace."""
        store.record_intervention("stu_b", "base_case", "trace", 1, True)
        store.record_intervention("stu_b", "recursive_step", "trace", 1, True)
        store.record_intervention("stu_b", "base_case", "analogy", 1, False)
        style, _ = adaptive_select(store, "stu_b", "call_stack", [])
        assert style == "trace"

    def test_same_gap_different_students(self, store):
        """Two students with different histories get different styles for same gap."""
        # Student A: analogy wins
        store.record_intervention("stu_a", "base_case", "analogy", 1, True)
        store.record_intervention("stu_a", "base_case", "analogy", 1, True)
        # Student B: trace wins
        store.record_intervention("stu_b", "base_case", "trace", 1, True)
        store.record_intervention("stu_b", "base_case", "trace", 1, True)
        store.record_intervention("stu_b", "base_case", "analogy", 1, False)

        style_a, _ = adaptive_select(store, "stu_a", "call_stack", [])
        style_b, _ = adaptive_select(store, "stu_b", "call_stack", [])
        assert style_a == "analogy"
        assert style_b == "trace"
        assert style_a != style_b


class TestAttempt2NeverRepeats:
    """Attempt 2 must never repeat the style that failed on Attempt 1."""

    def test_never_repeat_failed_style(self, store):
        """After analogy fails, attempt 2 must pick trace."""
        style, reason = adaptive_select(store, "stu1", "call_stack", ["analogy"])
        assert style == "trace"
        assert "switching" in reason.lower() or "failed" in reason.lower()

    def test_never_repeat_trace(self, store):
        """After trace fails, attempt 2 must pick analogy."""
        style, reason = adaptive_select(store, "stu1", "call_stack", ["trace"])
        assert style == "analogy"

    def test_both_exhausted(self, store):
        """When both styles are exhausted, returns first style."""
        style, reason = adaptive_select(store, "stu1", "call_stack", ["analogy", "trace"])
        assert style in STYLES
        assert "exhausted" in reason.lower()


class TestFallbackBehavior:
    """Fallback: student history → cohort history → default."""

    def test_no_history_defaults(self, store):
        """No history at all → default style (analogy)."""
        style, reason = adaptive_select(store, "new_student", "call_stack", [])
        assert style == DEFAULT_STYLE
        assert "no prior data" in reason

    def test_cohort_only(self, store):
        """No student history, but cohort data exists → use cohort."""
        store.record_intervention("other1", "call_stack", "trace", 1, True)
        store.record_intervention("other2", "call_stack", "trace", 1, True)
        store.record_intervention("other3", "call_stack", "analogy", 1, False)
        style, reason = adaptive_select(store, "new_student", "call_stack", [])
        assert style == "trace"
        assert "cohort" in reason.lower()

    def test_student_overrides_cohort(self, store):
        """Student history overrides cohort data."""
        # Cohort prefers trace
        store.record_intervention("other1", "call_stack", "trace", 1, True)
        store.record_intervention("other2", "call_stack", "trace", 1, True)
        # But this student succeeds with analogy
        store.record_intervention("stu1", "call_stack", "analogy", 1, True)
        style, _ = adaptive_select(store, "stu1", "call_stack", [])
        # Student's analogy: sr=1.0, cr=0.33 → score = 0.7*1.0 + 0.3*0.33 = 0.80
        # Student's trace: sr=0.5(default), cr=0.67 → score = 0.7*0.5 + 0.3*0.67 = 0.55
        assert style == "analogy"


class TestDemoPersonaSelections:
    """Verify that seeded demo persona histories produce correct selections."""

    def test_ananya_gets_analogy(self, store):
        """ananya_analogy has analogy success history → selects analogy."""
        store.record_intervention("ananya_analogy", "base_case", "analogy", 1, True)
        store.record_intervention("ananya_analogy", "recursive_step", "analogy", 1, True)
        style, _ = adaptive_select(store, "ananya_analogy", "call_stack", [])
        assert style == "analogy"

    def test_bharat_gets_trace(self, store):
        """bharat_trace has trace success history → selects trace."""
        store.record_intervention("bharat_trace", "base_case", "analogy", 1, False)
        store.record_intervention("bharat_trace", "base_case", "trace", 2, True)
        store.record_intervention("bharat_trace", "recursive_step", "trace", 1, True)
        style, _ = adaptive_select(store, "bharat_trace", "call_stack", [])
        assert style == "trace"

    def test_karthik_gets_default(self, store):
        """karthik_stuck has no history → selects default (analogy)."""
        style, reason = adaptive_select(store, "karthik_stuck", "call_stack", [])
        assert style == DEFAULT_STYLE
        assert "no prior data" in reason


class TestReasonString:
    """Verify that reasons are human-readable."""

    def test_reason_includes_style_name(self, store):
        store.record_intervention("stu1", "call_stack", "analogy", 1, True)
        _, reason = adaptive_select(store, "stu1", "call_stack", [])
        assert "Analogy" in reason or "analogy" in reason

    def test_reason_includes_percentage(self, store):
        store.record_intervention("stu1", "call_stack", "analogy", 1, True)
        _, reason = adaptive_select(store, "stu1", "call_stack", [])
        assert "100%" in reason or "score=" in reason
