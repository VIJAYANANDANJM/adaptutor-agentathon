"""
remediation/feedback.py — Targeted mistake diagnosis after a failed retest.

Generates concise, student-friendly explanations of why the learner's chosen
option was incorrect and provides a key memorable takeaway before adapting styles.
"""
from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel

from remediation.schema import RetestFeedback
from slice.budget import Budget
from slice.config import Settings

logger = logging.getLogger(__name__)


class MistakeAnalysisSchema(BaseModel):
    """Structured response schema for LLM mistake analysis."""
    why_wrong: str
    what_to_remember: str


KNOWN_CONCEPT_FEEDBACK = {
    "call_stack": {
        "why_wrong": (
            "You selected [{opt}] \"{selected_text}\". This assumes activation records "
            "return or clear immediately, but in recursion each function invocation maintains "
            "its own distinct frame on the call stack until the base case is reached."
        ),
        "what_to_remember": (
            "Every recursive invocation pushes a new frame onto the call stack. "
            "Frames only pop and return when unwinding begins."
        ),
    },
    "base_case": {
        "why_wrong": (
            "You selected [{opt}] \"{selected_text}\". Without a strictly verified termination "
            "guard, the function either executes infinitely or halts prematurely without returning "
            "the canonical base value."
        ),
        "what_to_remember": (
            "The base case is the non-recursive condition that halts recursion and provides the "
            "foundation for unwinding."
        ),
    },
    "recursive_step": {
        "why_wrong": (
            "You selected [{opt}] \"{selected_text}\". This choice does not properly decompose the "
            "problem into a smaller sub-problem, meaning the call chain cannot converge toward the base case."
        ),
        "what_to_remember": (
            "Each recursive call must strictly make progress by passing a strictly smaller or simpler "
            "argument toward the base case."
        ),
    },
    "return_propagation": {
        "why_wrong": (
            "You selected [{opt}] \"{selected_text}\". This choice overlooks how values computed at "
            "the deepest call stack level must bubble back up through each awaiting caller."
        ),
        "what_to_remember": (
            "Return values must propagate step-by-step up the call stack so each caller can "
            "incorporate the result."
        ),
    },
}


def get_deterministic_feedback(
    concept: str,
    selected_option: str,
    selected_text: str,
    correct_option: str,
    correct_text: str,
    question_text: str = "",
) -> tuple[str, str]:
    """Provide a deterministic, mistake-specific explanation and takeaway."""
    opt = selected_option.upper()
    correct_opt = correct_option.upper()
    concept_key = concept.lower().strip()
    concept_name = concept.replace("_", " ").title()

    if concept_key in KNOWN_CONCEPT_FEEDBACK:
        template = KNOWN_CONCEPT_FEEDBACK[concept_key]
        why_wrong = template["why_wrong"].format(
            opt=opt,
            selected_text=selected_text,
            correct_opt=correct_opt,
            correct_text=correct_text,
        )
        what_to_remember = template["what_to_remember"]
        return why_wrong, what_to_remember

    # Dynamic fallback for arbitrary topics (DB normalization, IoT MQTT, OS virtual memory, etc.)
    why_wrong = (
        f"You selected [{opt}] \"{selected_text}\". This option is incorrect because it violates the "
        f"core principles of {concept_name}, whereas [{correct_opt}] \"{correct_text}\" represents "
        f"the valid approach."
    )
    what_to_remember = (
        f"For {concept_name}, focus on why [{correct_opt}] correctly satisfies the rule rather than "
        f"the invalid condition described in [{opt}]."
    )
    return why_wrong, what_to_remember


def generate_retest_feedback(
    *,
    student_id: str,
    concept: str,
    attempt: int,
    selected_option: str,
    correct_option: str,
    question_text: str,
    options: dict[str, str],
    previous_style: str,
    settings: Settings,
    budget: Budget,
    topic: str = "",
) -> RetestFeedback:
    """Diagnose the student's retest error using real LLM or deterministic fallback."""
    clean_sel = (selected_option or "").strip().lower()
    clean_corr = (correct_option or "").strip().lower()

    selected_text = options.get(clean_sel, options.get(selected_option, selected_option or "None"))
    correct_text = options.get(clean_corr, options.get(correct_option, correct_option or "None"))
    concept_name = concept.replace("_", " ").title()
    topic_str = topic or "Computer Science"

    # Default fallback content
    fb_why_wrong, fb_remember = get_deterministic_feedback(
        concept=concept,
        selected_option=clean_sel,
        selected_text=selected_text,
        correct_option=clean_corr,
        correct_text=correct_text,
        question_text=question_text,
    )
    source = "fallback"

    if settings.llm_mode == "real":
        try:
            from slice import llm

            # Format options block with explicit indicators
            opts_lines = []
            for k, v in options.items():
                tag = ""
                if k.strip().lower() == clean_corr:
                    tag = "  <-- [CORRECT ANSWER]"
                elif k.strip().lower() == clean_sel:
                    tag = "  <-- [STUDENT'S WRONG CHOICE]"
                opts_lines.append(f"  [{k.upper()}] {v}{tag}")
            options_block = "\n".join(opts_lines)

            system_prompt = (
                "You are an encouraging, expert computer science tutor. A student just "
                "answered a retest question incorrectly.\n\n"
                "Your task:\n"
                "1. Diagnose the specific misconception behind their chosen option.\n"
                "2. In 'why_wrong', explain specifically why selecting their option was incorrect. "
                "Directly reference their choice and explain the flaw in that reasoning (under 50 words).\n"
                "3. In 'what_to_remember', give a single concrete, memorable rule or principle to avoid "
                "this mistake (under 25 words).\n"
                "4. Do NOT lecture about the whole concept. Keep it tightly focused on their specific mistake."
            )

            user_prompt = (
                f"Topic: {topic_str}\n"
                f"Concept: {concept_name}\n"
                f"Previous Explanation Style: {previous_style.title()} (Attempt {attempt})\n\n"
                f"Retest Question:\n\"{question_text}\"\n\n"
                f"Options:\n{options_block}\n\n"
                f"Student Selected: [{clean_sel.upper()}] \"{selected_text}\"\n"
                f"Correct Answer:   [{clean_corr.upper()}] \"{correct_text}\"\n\n"
                f"Diagnose their mistake now."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            result = llm.complete(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=MistakeAnalysisSchema,
                step=f"feedback_{concept}_att{attempt}",
            )

            if isinstance(result, MistakeAnalysisSchema):
                fb_why_wrong = result.why_wrong.strip()
                fb_remember = result.what_to_remember.strip()
                source = "llm"
            elif hasattr(result, "why_wrong") and hasattr(result, "what_to_remember"):
                fb_why_wrong = str(result.why_wrong).strip()
                fb_remember = str(result.what_to_remember).strip()
                source = "llm"

        except Exception as e:
            logger.warning(
                f"[RetestFeedback Warning] LLM generation failed ({type(e).__name__}: {e}). "
                "Using deterministic feedback fallback."
            )
            # Retain deterministic feedback fallback
            source = "fallback"

    return RetestFeedback(
        student_id=student_id,
        concept=concept,
        attempt=attempt,
        selected_option=clean_sel.upper(),
        selected_text=selected_text,
        correct_option=clean_corr.upper(),
        correct_text=correct_text,
        why_wrong=fb_why_wrong,
        what_to_remember=fb_remember,
        source=source,
    )
