"""
ExplanationProvider interface and implementations.

MockExplanationProvider: deterministic, zero-network canned responses.
RealLLMExplanationProvider: calls slice.llm.complete() via OpenRouter.

Both count against the call budget.
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


class MockExplanationProvider(ExplanationProvider):
    """Returns deterministic, style-specific canned responses. Zero network.
    Still counts against the call budget so budget fences are testable."""

    MOCK_EXPLANATIONS = {
        ("call_stack", "analogy"): (
            "Think of the call stack like a stack of cafeteria trays. Each time "
            "a function calls itself, a new tray goes on top. The base case itself "
            "occupies a frame — so you need to count it too. For factorial(4), "
            "that means 5 trays total: factorial(4), factorial(3), factorial(2), "
            "factorial(1), and factorial(0)."
        ),
        ("call_stack", "trace"): (
            "Let's trace the execution step by step:\n\n"
            "| call            | n | action                  | frames on stack |\n"
            "|-----------------|---|-------------------------|-----------------|\n"
            "| factorial(4)    | 4 | calls factorial(3)      | 1               |\n"
            "| factorial(3)    | 3 | calls factorial(2)      | 2               |\n"
            "| factorial(2)    | 2 | calls factorial(1)      | 3               |\n"
            "| factorial(1)    | 1 | calls factorial(0)      | 4               |\n"
            "| factorial(0)    | 0 | base case, returns 1    | 5 ← deepest     |\n\n"
            "Count the frames at the deepest point: 5."
        ),
        ("base_case", "analogy"): (
            "The base case is like the ground floor of a building. When the elevator "
            "(recursion) reaches the ground floor, it stops going down. Without a "
            "ground floor, the elevator would keep descending forever. In recursion, "
            "the base case tells the function when to stop calling itself."
        ),
        ("base_case", "trace"): (
            "Let's trace factorial(3):\n"
            "factorial(3) → checks: is n == 0? No → calls factorial(2)\n"
            "factorial(2) → checks: is n == 0? No → calls factorial(1)\n"
            "factorial(1) → checks: is n == 0? No → calls factorial(0)\n"
            "factorial(0) → checks: is n == 0? YES → returns 1 (STOPS HERE)\n\n"
            "The base case n == 0 is what stops the chain of calls."
        ),
        ("recursive_step", "analogy"): (
            "Think of the recursive step like a chain of workers. Each worker does "
            "a small piece of work and passes the rest to the next worker. In "
            "f(n) = n + f(n-1), each worker adds their number n and asks the next "
            "worker (n-1) to compute the rest. The total is the sum of all their contributions."
        ),
        ("recursive_step", "trace"): (
            "Let's trace f(3) where f(n) = n + f(n-1), f(0) = 0:\n"
            "f(3) = 3 + f(2)\n"
            "f(2) = 2 + f(1)\n"
            "f(1) = 1 + f(0)\n"
            "f(0) = 0\n\n"
            "Now unwind: f(1) = 1+0 = 1, f(2) = 2+1 = 3, f(3) = 3+3 = 6.\n"
            "Each call contributes its own n to the total."
        ),
        ("return_propagation", "analogy"): (
            "Imagine a line of people whispering a number back. The person at the "
            "end (base case) whispers 1 to the person before them. Each person "
            "multiplies what they hear by their own number and whispers the result "
            "back. factorial(1) returns 1 to factorial(2), which computes 2×1=2 "
            "and passes that back."
        ),
        ("return_propagation", "trace"): (
            "Trace factorial(3) return values:\n"
            "factorial(0) returns 1\n"
            "factorial(1) receives 1, returns 1 × 1 = 1\n"
            "factorial(2) receives 1, returns 2 × 1 = 2\n"
            "factorial(3) receives 2, returns 3 × 2 = 6\n\n"
            "Each level takes the return value from below and multiplies by n."
        ),
    }

    def explain(self, *, student_id: str, concept: str, style: str,
                wrong_answer: str, correct_answer: str,
                question_text: str, budget: Budget,
                settings: Settings) -> ExplanationPayload:
        budget.check_tokens()
        budget.record_tokens(0)

        text = self.MOCK_EXPLANATIONS.get(
            (concept, style),
            f"[Mock {style} explanation for {concept}]"
        )

        return ExplanationPayload(
            student_id=student_id,
            concept=concept,
            style=style,
            text=text,
        )


class RealLLMExplanationProvider(ExplanationProvider):
    """Calls slice.llm.complete() via OpenRouter for real explanations."""

    def explain(self, *, student_id: str, concept: str, style: str,
                wrong_answer: str, correct_answer: str,
                question_text: str, budget: Budget,
                settings: Settings) -> ExplanationPayload:
        from slice import llm

        prompt_dir = Path(__file__).parent / "prompts"
        prompt_file = prompt_dir / f"{style}.md"
        style_instruction = prompt_file.read_text() if prompt_file.exists() else ""

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

        try:
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
        except Exception as e:
            # Resilient fallback: deliver a clean explanation rather than crashing the session
            print(f"  [AI Tutor Warning] Live model call encountered '{type(e).__name__}'. Using fallback remediation.")
            mock = MockExplanationProvider()
            return mock.explain(
                student_id=student_id,
                concept=concept,
                style=style,
                wrong_answer=wrong_answer,
                correct_answer=correct_answer,
                question_text=question_text,
                budget=budget,
                settings=settings,
            )


def get_provider(mode: str) -> ExplanationProvider:
    """Factory: returns MockExplanationProvider or RealLLMExplanationProvider."""
    if mode == "real":
        return RealLLMExplanationProvider()
    return MockExplanationProvider()
