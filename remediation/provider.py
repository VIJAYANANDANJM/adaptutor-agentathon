"""
ExplanationProvider interface and implementations.

RealLLMExplanationProvider: calls slice.llm.complete() via OpenRouter.
All model calls count against the call budget.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from remediation.schema import ExplanationPayload
from slice.budget import Budget
from slice.config import Settings


class ExplanationProvider(ABC):
    @abstractmethod
    def explain(self, *, student_id: str, concept: str, style: str,
                wrong_answer: str, correct_answer: str,
                question_text: str, budget: Budget,
                settings: Settings) -> ExplanationPayload:
        ...


class RealLLMExplanationProvider(ExplanationProvider):
    """Calls slice.llm.complete() via OpenRouter for real explanations."""

    def explain(self, *, student_id: str, concept: str, style: str,
                wrong_answer: str, correct_answer: str,
                question_text: str, budget: Budget,
                settings: Settings) -> ExplanationPayload:
        from slice import llm

        prompt_dir = Path(__file__).parent / "prompts"
        prompt_file = prompt_dir / f"{style}.md"
        style_instruction = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""

        messages = [
            {"role": "system", "content": (
                "You are a patient CS tutor helping a second-year B.E. CSE student "
                "understand recursion in Python. You must explain using the specified style. "
                "Be concise and specific to the student's error.\n\n"
                f"Style instructions:\n{style_instruction}"
            )},
            {"role": "user", "content": (
                f"The student answered '{wrong_answer}' to the question:\n"
                f"{question_text}\n\n"
                f"The correct answer is '{correct_answer}'.\n"
                f"The concept being tested is: {concept}.\n\n"
                f"Generate a clear explanation using the '{style}' style that helps "
                f"the student understand why their answer was wrong and what the "
                f"correct reasoning is. Return a JSON object with fields: "
                f"student_id, concept, style, text."
            )},
        ]

        result = llm.complete(
            settings=settings,
            budget=budget,
            messages=messages,
            schema=ExplanationPayload,
            step=f"explain_{concept}_{style}",
        )

        if isinstance(result, ExplanationPayload):
            result.student_id = student_id
            return result

        return ExplanationPayload(
            student_id=student_id,
            concept=concept,
            style=style,
            text=str(result),
        )


def get_provider(mode: str = "real") -> ExplanationProvider:
    """Factory: returns RealLLMExplanationProvider."""
    return RealLLMExplanationProvider()
