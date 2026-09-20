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
                settings: Settings,
                options: dict[str, str] | None = None,
                attempt: int = 1,
                mastery_pct: int | None = None,
                previous_styles: list[str] | None = None,
                topic: str = "",
                style_instruction: str = "",
                **kwargs: Any) -> ExplanationPayload:
        ...


class RealLLMExplanationProvider(ExplanationProvider):
    """Calls slice.llm.complete() via OpenRouter for real explanations."""

    CONCEPT_DESCRIPTIONS = {
        "base_case": "The condition that halts recursion and prevents infinite execution loops.",
        "recursive_step": "Decomposing the problem into smaller sub-problems through self-referential calls.",
        "call_stack": "Stack frames and activation records pushed on invocation and popped on return.",
        "return_propagation": "Passing return values back up through the call stack to assemble the final result.",
    }

    def explain(self, *, student_id: str, concept: str, style: str,
                wrong_answer: str, correct_answer: str,
                question_text: str, budget: Budget,
                settings: Settings,
                options: dict[str, str] | None = None,
                attempt: int = 1,
                mastery_pct: int | None = None,
                previous_styles: list[str] | None = None,
                topic: str = "",
                style_instruction: str = "",
                **kwargs: Any) -> ExplanationPayload:
        from slice import llm

        if not style_instruction:
            prompt_dir = Path(__file__).parent / "prompts"
            prompt_file = prompt_dir / f"{style}.md"
            style_instruction = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else f"Explain clearly using {style} approach."

        concept_name = concept.replace("_", " ").title()
        concept_desc = self.CONCEPT_DESCRIPTIONS.get(concept, "")
        topic_str = topic or "recursion in Python"

        # Format options and identify full option text
        opts = options or {}
        wrong_key = wrong_answer.strip().lower()
        correct_key = correct_answer.strip().lower()
        wrong_text = opts.get(wrong_key, opts.get(wrong_answer, wrong_answer))
        correct_text = opts.get(correct_key, opts.get(correct_answer, correct_answer))

        if opts:
            options_lines = []
            for k, v in opts.items():
                tag = ""
                if k.strip().lower() == correct_key:
                    tag = "  <-- [CORRECT ANSWER]"
                elif k.strip().lower() == wrong_key:
                    tag = "  <-- [STUDENT'S WRONG CHOICE]"
                options_lines.append(f"  [{k.upper()}] {v}{tag}")
            options_block = "\n".join(options_lines)
        else:
            options_block = f"  Student chose: {wrong_answer}\n  Correct answer: {correct_answer}"

        # Context about student attempts & mastery
        context_notes = []
        if attempt > 1:
            context_notes.append(f"Remediation Attempt: {attempt} of 2 (The student previously struggled after an earlier explanation; provide a fresh, crystal-clear perspective).")
            if previous_styles:
                context_notes.append(f"Styles already tried that failed: {', '.join(s.title() for s in previous_styles)}.")
        else:
            context_notes.append("Remediation Attempt: 1 of 2 (Initial intervention).")

        if mastery_pct is not None:
            context_notes.append(f"Student's Current Concept Mastery: {mastery_pct}%.")

        context_header = "\n".join(context_notes)

        messages = [
            {"role": "system", "content": (
                f"You are a patient, expert university CS tutor helping a student "
                f"master {topic_str}.\n\n"
                f"Pedagogical Guidelines ({style.title()}):\n{style_instruction}"
            )},
            {"role": "user", "content": (
                f"Topic: {topic_str}\n"
                f"Concept: {concept_name}" + (f" ({concept_desc})" if concept_desc else "") + f"\n"
                f"{context_header}\n\n"
                f"Diagnostic Question:\n\"{question_text}\"\n\n"
                f"Options:\n{options_block}\n\n"
                f"Student Selected: [{wrong_answer.upper()}] \"{wrong_text}\"\n"
                f"Correct Answer:   [{correct_answer.upper()}] \"{correct_text}\"\n\n"
                f"Pedagogical Task:\n"
                f"1. Explain specifically why choosing [{wrong_answer.upper()}] \"{wrong_text}\" is incorrect.\n"
                f"2. Explain why [{correct_answer.upper()}] \"{correct_text}\" is the correct reasoning.\n"
                f"3. Strictly adhere to the '{style}' pedagogical style rules provided in system instructions.\n"
                f"4. Keep the explanation clear, focused, and under 300 words without unnecessary fluff.\n\n"
                f"Return a JSON object with fields:\n"
                f"  \"student_id\": \"{student_id}\",\n"
                f"  \"concept\": \"{concept}\",\n"
                f"  \"style\": \"{style}\",\n"
                f"  \"text\": \"<your explanation>\""
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
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                f"[ExplanationProvider Warning] LLM call failed ({type(exc).__name__}: {exc}). "
                "Using pedagogical fallback explanation."
            )
            fallback_text = (
                f"**Understanding {concept_name}** ({style.title()} perspective):\n\n"
                f"Your selected answer [{wrong_answer.upper()}] \"{wrong_text}\" is incorrect.\n\n"
                f"The correct principle is [{correct_answer.upper()}]: \"{correct_text}\".\n\n"
                f"{concept_desc if concept_desc else f'Review the fundamental rules of {concept_name} in {topic_str}.'}"
            )
            return ExplanationPayload(
                student_id=student_id,
                concept=concept,
                style=style,
                text=fallback_text,
            )


def get_provider(mode: str = "real") -> ExplanationProvider:
    """Factory: always returns RealLLMExplanationProvider.

    Raises:
        ValueError: if *mode* is anything other than "real", so that an
            invalid environment configuration (e.g. LLM_MODE=mock left over
            from an old .env) is caught early rather than silently proceeding.
    """
    if mode != "real":
        raise ValueError(
            f"Invalid provider mode {mode!r}. "
            "Only LLM_MODE=real is supported. "
            "Check your .env or environment variables."
        )
    return RealLLMExplanationProvider()
