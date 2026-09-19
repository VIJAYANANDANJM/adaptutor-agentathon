"""
Fixed 8-question assessment and fixed retest question bank.

Loads curated curriculum questions from data/quiz.json and
data/retest_questions.json.

NEVER generate assessment or retest questions via LLM. All questions are curated
by the instructor and fixed at deployment time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    concept: str
    text: str
    options: dict[str, str]
    correct: str


@dataclass(frozen=True)
class RetestQuestion:
    concept: str
    text: str
    options: dict[str, str]
    correct: str


# ── Load Fixed 8-question assessment from data/quiz.json ────────────────────

def _load_quiz_questions() -> list[QuizQuestion]:
    quiz_file = DATA_DIR / "quiz.json"
    with open(quiz_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        QuizQuestion(
            id=item["id"],
            concept=item["concept"],
            text=item["text"],
            options=item["options"],
            correct=item["correct"],
        )
        for item in data
    ]


QUIZ_QUESTIONS: list[QuizQuestion] = _load_quiz_questions()

ANSWER_KEY: dict[str, str] = {q.id: q.correct for q in QUIZ_QUESTIONS}
QUESTION_CONCEPT: dict[str, str] = {q.id: q.concept for q in QUIZ_QUESTIONS}
QUESTION_BY_ID: dict[str, QuizQuestion] = {q.id: q for q in QUIZ_QUESTIONS}

ALL_CONCEPTS = ["base_case", "recursive_step", "call_stack", "return_propagation"]


# ── Load Fixed retest questions from data/retest_questions.json ─────────────

def _load_retest_questions() -> tuple[dict[str, RetestQuestion], dict[str, RetestQuestion]]:
    retest_file = DATA_DIR / "retest_questions.json"
    with open(retest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    attempt_1 = {
        concept: RetestQuestion(
            concept=q["concept"],
            text=q["text"],
            options=q["options"],
            correct=q["correct"],
        )
        for concept, q in data["attempt_1"].items()
    }
    attempt_2 = {
        concept: RetestQuestion(
            concept=q["concept"],
            text=q["text"],
            options=q["options"],
            correct=q["correct"],
        )
        for concept, q in data["attempt_2"].items()
    }
    return attempt_1, attempt_2


RETEST_QUESTIONS, RETEST_VARIANTS = _load_retest_questions()


def get_retest_question(concept: str, attempt: int) -> RetestQuestion:
    """Get the retest question for a concept. Attempt 1 uses RETEST_QUESTIONS,
    attempt 2 uses RETEST_VARIANTS."""
    if attempt <= 1:
        return RETEST_QUESTIONS[concept]
    return RETEST_VARIANTS[concept]
