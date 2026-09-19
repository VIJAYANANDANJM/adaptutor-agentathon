"""
Deterministic canned responses for test personas and demo personas.

These stubs simulate student answers for automated end-to-end testing
and for the `python run.py demo` command.
Zero tokens consumed — no network, no API keys.
"""
from __future__ import annotations


PERSONA_QUIZ_ANSWERS = {
    # ── Test personas (existing) ──
    "priya_22cs031": {
        "Q1": "a", "Q2": "b", "Q3": "b", "Q4": "b",
        "Q5": "a", "Q6": "c", "Q7": "a", "Q8": "a",
    },
    "ravi_22cs044": {
        "Q1": "a", "Q2": "b", "Q3": "b", "Q4": "b",
        "Q5": "a", "Q6": "c", "Q7": "c", "Q8": "a",
    },
    "karthik_22cs012": {
        "Q1": "a", "Q2": "b", "Q3": "b", "Q4": "b",
        "Q5": "a", "Q6": "c", "Q7": "a", "Q8": "a",
    },
    # ── Demo personas (used by `python run.py demo`) ──
    # All three fail only Q5 (call_stack): answer "a" instead of correct "b"
    "ananya_analogy": {
        "Q1": "a", "Q2": "b", "Q3": "b", "Q4": "b",
        "Q5": "a", "Q6": "c", "Q7": "a", "Q8": "a",
    },
    "bharat_trace": {
        "Q1": "a", "Q2": "b", "Q3": "b", "Q4": "b",
        "Q5": "a", "Q6": "c", "Q7": "a", "Q8": "a",
    },
    "karthik_stuck": {
        "Q1": "a", "Q2": "b", "Q3": "b", "Q4": "b",
        "Q5": "a", "Q6": "c", "Q7": "a", "Q8": "a",
    },
}


PERSONA_RETEST_ANSWERS: dict[str, dict[str, dict[str, str]]] = {
    # ── Test personas (existing) ──
    "priya_22cs031": {
        "call_stack": {
            "analogy_1": "b",   # correct on first attempt with analogy
        },
    },
    "ravi_22cs044": {
        "call_stack": {
            "analogy_1": "a",   # wrong on first attempt with analogy
            "trace_2": "b",     # correct on second attempt with trace
        },
        "return_propagation": {
            "analogy_1": "b",   # correct on first attempt with analogy
            "trace_1": "b",     # correct on first attempt with trace (adaptive selector may pick this)
        },
    },
    "karthik_22cs012": {
        "call_stack": {
            "analogy_1": "a",   # wrong on first attempt with analogy
            "trace_2": "a",     # wrong on second attempt with trace → instructor flag
        },
    },
    # ── Demo personas ──
    "ananya_analogy": {
        "call_stack": {
            "analogy_1": "b",   # correct on attempt 1 with analogy (her strength)
            "trace_1": "b",     # also correct with trace (fallback)
        },
    },
    "bharat_trace": {
        "call_stack": {
            "trace_1": "b",     # correct on attempt 1 with trace (his strength)
            "analogy_1": "a",   # wrong with analogy
        },
    },
    "karthik_stuck": {
        "call_stack": {
            "trace_1": "a",     # wrong on attempt 1 with trace
            "analogy_1": "a",   # wrong on attempt 1 with analogy
            "analogy_2": "a",   # wrong on attempt 2 with analogy → escalates
            "trace_2": "a",     # wrong on attempt 2 with trace → escalates
        },
    },
}


def get_quiz_answers(student_id: str) -> dict[str, str] | None:
    """Returns the predetermined quiz answers for a test persona, or None."""
    return PERSONA_QUIZ_ANSWERS.get(student_id)


def get_retest_answer(student_id: str, concept: str, style: str, attempt: int) -> str | None:
    """Returns the predetermined retest answer for a persona's concept+style+attempt."""
    student_data = PERSONA_RETEST_ANSWERS.get(student_id, {})
    concept_data = student_data.get(concept, {})
    key = f"{style}_{attempt}"
    return concept_data.get(key)
