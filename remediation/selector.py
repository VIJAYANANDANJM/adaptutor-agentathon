"""
Evidence-based adaptive intervention selector.

Deterministic code — not a model — selects the explanation style.
The LLM must NEVER select the style.

Formula:
    Score(style) = 0.7 × StudentPersonalSuccessRate(style)
                 + 0.3 × CohortSuccessRate(style)

Policy:
    Attempt 1: Pick highest-scoring style. Fall back to cohort, then default.
    Attempt 2: Never repeat the style that just failed on Attempt 1.
               Pick the next highest-scoring style.
"""
from __future__ import annotations

from typing import Any

from slice.store import Store

STYLES = ["analogy", "trace"]
DEFAULT_STYLE = "analogy"
DEFAULT_RATE = 0.5  # neutral prior for styles with no history


def adaptive_select(
    store: Store,
    student_id: str,
    concept: str,
    styles_tried: list[str],
    available_styles: list[str] | None = None,
    default_style: str | None = None,
) -> tuple[str, str]:
    """Pick the best explanation style for a concept.

    Returns (selected_style, human_readable_reason).
    """
    style_pool = available_styles if available_styles is not None else STYLES
    def_style = default_style or (style_pool[0] if style_pool else DEFAULT_STYLE)
    available = [s for s in style_pool if s not in styles_tried]

    # Edge cases
    if len(available) == 1:
        failed = styles_tried[0] if styles_tried else "none"
        return (
            available[0],
            f"Previous style ({failed}) failed; switching to {available[0]}.",
        )
    if not available:
        return def_style, "Both styles exhausted."

    # ── Compute scores ─────────────────────────────────────────────────
    scores: dict[str, float] = {}
    reasons_parts: list[str] = []

    for style in available:
        student_rate = store.get_student_style_rate(student_id, style)
        cohort_rate = store.get_cohort_style_rate(style)

        sr = student_rate if student_rate is not None else DEFAULT_RATE
        cr = cohort_rate if cohort_rate is not None else DEFAULT_RATE

        score = 0.7 * sr + 0.3 * cr
        scores[style] = score

        # Build human-readable reason parts
        sr_str = f"{int(sr * 100)}%" if student_rate is not None else "no data"
        cr_str = f"{int(cr * 100)}%" if cohort_rate is not None else "no data"
        reasons_parts.append(
            f"{style.title()}: student={sr_str}, cohort={cr_str}, score={score:.2f}"
        )

    # Select the highest scoring style, with tie-break toward default style
    best = max(available, key=lambda s: (scores[s], s == def_style))

    # Build reason string
    student_eff = store.get_style_efficacy(student_id)
    history_parts = []
    for style in available:
        if style in student_eff:
            e = student_eff[style]
            pct = int(e["rate"] * 100)
            history_parts.append(f"{style.title()}: {e['wins']}/{e['total']} ({pct}%)")
        else:
            history_parts.append(f"{style.title()}: no history")

    if student_eff:
        best_eff = student_eff.get(best)
        if best_eff and best_eff["total"] > 0:
            pct = int(best_eff["rate"] * 100)
            reason = (
                f"Student has {pct}% past success with {best.title()}. "
                f"[{'; '.join(reasons_parts)}]"
            )
        else:
            reason = (
                f"Highest composite score for {best.title()}. "
                f"[{'; '.join(reasons_parts)}]"
            )
    else:
        # No student history at all — check cohort
        any_cohort = any(
            store.get_cohort_style_rate(s) is not None for s in available
        )
        if any_cohort:
            reason = (
                f"No student history; using cohort data. Best: {best.title()}. "
                f"[{'; '.join(reasons_parts)}]"
            )
        else:
            reason = f"no prior data for {concept}; defaulting to {def_style}."
            best = def_style

    return best, reason
