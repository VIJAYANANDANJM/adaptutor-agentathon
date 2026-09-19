"""
Fixed 8-question assessment and fixed retest question bank.

NEVER generate assessment or retest questions via LLM. All questions are curated
by the instructor and fixed at deployment time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    concept: str
    text: str
    options: dict[str, str]
    correct: str


# ── Fixed 8-question assessment (from AgentSpec Section 4) ──────────────────

QUIZ_QUESTIONS: list[QuizQuestion] = [
    QuizQuestion(
        id="Q1", concept="base_case",
        text="What is the base case in factorial(n)?",
        options={"a": "n == 0", "b": "n == 1", "c": "n < 0", "d": "none"},
        correct="a",
    ),
    QuizQuestion(
        id="Q2", concept="base_case",
        text="What happens if countdown(n) has no base case?",
        options={"a": "returns 0", "b": "infinite recursion", "c": "returns n", "d": "syntax error"},
        correct="b",
    ),
    QuizQuestion(
        id="Q3", concept="recursive_step",
        text="Given def f(n): return n + f(n-1) with f(0)=0, what is f(3)?",
        options={"a": "3", "b": "6", "c": "9", "d": "0"},
        correct="b",
    ),
    QuizQuestion(
        id="Q4", concept="recursive_step",
        text="In sum_list([3,1,4]), how many times is sum_list called in total?",
        options={"a": "3", "b": "4", "c": "2", "d": "1"},
        correct="b",
    ),
    QuizQuestion(
        id="Q5", concept="call_stack",
        text="At the deepest point of factorial(4), how many frames are on the stack?",
        options={"a": "4", "b": "5", "c": "3", "d": "1"},
        correct="b",
    ),
    QuizQuestion(
        id="Q6", concept="call_stack",
        text="What is the first frame removed from the stack during factorial(3)?",
        options={"a": "factorial(3)", "b": "factorial(1)", "c": "factorial(0)", "d": "factorial(2)"},
        correct="c",
    ),
    QuizQuestion(
        id="Q7", concept="return_propagation",
        text="In factorial(3), what does factorial(1) return to factorial(2)?",
        options={"a": "1", "b": "2", "c": "3", "d": "6"},
        correct="a",
    ),
    QuizQuestion(
        id="Q8", concept="return_propagation",
        text="In fib(4) (naive), what value does fib(2) return?",
        options={"a": "1", "b": "2", "c": "0", "d": "3"},
        correct="a",
    ),
]

ANSWER_KEY: dict[str, str] = {q.id: q.correct for q in QUIZ_QUESTIONS}
QUESTION_CONCEPT: dict[str, str] = {q.id: q.concept for q in QUIZ_QUESTIONS}
QUESTION_BY_ID: dict[str, QuizQuestion] = {q.id: q for q in QUIZ_QUESTIONS}

ALL_CONCEPTS = ["base_case", "recursive_step", "call_stack", "return_propagation"]


# ── Fixed retest questions (one per concept, different surface details) ──────

@dataclass(frozen=True)
class RetestQuestion:
    concept: str
    text: str
    options: dict[str, str]
    correct: str


RETEST_QUESTIONS: dict[str, RetestQuestion] = {
    "base_case": RetestQuestion(
        concept="base_case",
        text=(
            "In def power(x, n): if n == 0: return 1; return x * power(x, n-1), "
            "what is the base case?"
        ),
        options={"a": "n == 1", "b": "n == 0", "c": "x == 0", "d": "x == 1"},
        correct="b",
    ),
    "recursive_step": RetestQuestion(
        concept="recursive_step",
        text=(
            "Given def multiply(a, b): if b == 0: return 0; return a + multiply(a, b-1), "
            "what is multiply(3, 4)?"
        ),
        options={"a": "7", "b": "12", "c": "9", "d": "0"},
        correct="b",
    ),
    "call_stack": RetestQuestion(
        concept="call_stack",
        text=(
            "At the deepest point of power(2, 3) where power(x, n) calls "
            "power(x, n-1) with base case n == 0, how many frames are on the stack?"
        ),
        options={"a": "3", "b": "4", "c": "5", "d": "2"},
        correct="b",
    ),
    "return_propagation": RetestQuestion(
        concept="return_propagation",
        text=(
            "In power(2, 3), what does power(2, 1) return to power(2, 2)?"
        ),
        options={"a": "1", "b": "2", "c": "4", "d": "8"},
        correct="b",
    ),
}

# Variant retest questions for the backward loop (attempt 2, different from attempt 1)
RETEST_VARIANTS: dict[str, RetestQuestion] = {
    "base_case": RetestQuestion(
        concept="base_case",
        text=(
            "In def gcd(a, b): if b == 0: return a; return gcd(b, a % b), "
            "what is the base case?"
        ),
        options={"a": "a == 0", "b": "b == 0", "c": "a == b", "d": "a % b == 0"},
        correct="b",
    ),
    "recursive_step": RetestQuestion(
        concept="recursive_step",
        text=(
            "Given def count_down(n): if n == 0: return 0; return 1 + count_down(n-1), "
            "what is count_down(5)?"
        ),
        options={"a": "4", "b": "5", "c": "6", "d": "0"},
        correct="b",
    ),
    "call_stack": RetestQuestion(
        concept="call_stack",
        text=(
            "In sum_to(5) where sum_to(n) calls sum_to(n-1) with base case n == 0, "
            "how many frames are on the stack at the deepest point?"
        ),
        options={"a": "5", "b": "6", "c": "4", "d": "7"},
        correct="b",
    ),
    "return_propagation": RetestQuestion(
        concept="return_propagation",
        text=(
            "In sum_to(3), what does sum_to(1) return to sum_to(2)?"
        ),
        options={"a": "1", "b": "3", "c": "2", "d": "0"},
        correct="a",
    ),
}


def get_retest_question(concept: str, attempt: int) -> RetestQuestion:
    """Get the retest question for a concept. Attempt 1 uses RETEST_QUESTIONS,
    attempt 2 uses RETEST_VARIANTS."""
    if attempt <= 1:
        return RETEST_QUESTIONS[concept]
    return RETEST_VARIANTS[concept]
