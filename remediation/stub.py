"""
Deterministic canned responses for the three test personas.

These stubs simulate student answers for automated end-to-end testing.
Zero tokens consumed — no network, no API keys.
"""
from __future__ import annotations


PERSONA_QUIZ_ANSWERS = {
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
}


PERSONA_RETEST_ANSWERS: dict[str, dict[str, dict[str, str]]] = {
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
        },
    },
    "karthik_22cs012": {
        "call_stack": {
            "analogy_1": "a",   # wrong on first attempt with analogy
            "trace_2": "a",     # wrong on second attempt with trace → instructor flag
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
