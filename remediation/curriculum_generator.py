"""
AI Curriculum Generator using OpenRouter / slice.llm.

Generates complete, validated curriculum modules (diagnostic quiz + retests +
pedagogical styles) for ANY topic or course provided by an instructor.
"""
from __future__ import annotations

import json
import re
from typing import Any
from pydantic import BaseModel, Field

from remediation.curriculum import CurriculumModule, save_module
from slice.config import Settings, settings as get_settings


class GeneratedQuestion(BaseModel):
    id: str
    concept: str
    text: str
    options: dict[str, str]
    correct: str


class GeneratedRetest(BaseModel):
    concept: str
    text: str
    options: dict[str, str]
    correct: str


class GeneratedModuleSchema(BaseModel):
    module_id: str
    title: str
    description: str
    concepts: list[str]
    concept_names: dict[str, str]
    available_styles: list[str]
    default_style: str
    style_descriptions: dict[str, str]
    quiz: list[GeneratedQuestion]
    retest_attempt_1: list[GeneratedRetest]
    retest_attempt_2: list[GeneratedRetest]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "_", slug).strip("_")


def _generate_mock_module(topic: str, description: str = "") -> dict[str, Any]:
    """Deterministic offline curriculum generator for testing and mock mode."""
    slug = _slugify(topic)[:25] or "custom_topic"
    c1 = f"{slug}_fundamentals"
    c2 = f"{slug}_core_rules"
    c3 = f"{slug}_edge_cases"
    c4 = f"{slug}_advanced_flow"

    concepts = [c1, c2, c3, c4]
    concept_names = {
        c1: f"{topic.title()} Fundamentals",
        c2: f"{topic.title()} Core Rules",
        c3: f"{topic.title()} Edge Cases",
        c4: f"{topic.title()} Advanced Application",
    }

    quiz = []
    q_idx = 1
    for c in concepts:
        quiz.append({
            "id": f"Q{q_idx}",
            "concept": c,
            "text": f"What is the defining characteristic of {concept_names[c]}?",
            "options": {
                "a": f"A primary requirement of {concept_names[c]}",
                "b": f"An invalid anti-pattern in {concept_names[c]}",
                "c": f"An unrelated secondary factor",
                "d": "None of the above"
            },
            "correct": "a"
        })
        q_idx += 1
        quiz.append({
            "id": f"Q{q_idx}",
            "concept": c,
            "text": f"Which scenario demonstrates a violation of {concept_names[c]}?",
            "options": {
                "a": f"Properly adhering to {concept_names[c]}",
                "b": f"Ignoring the constraints of {concept_names[c]}",
                "c": "Default initialization",
                "d": "Normal operation"
            },
            "correct": "b"
        })
        q_idx += 1

    retest_1 = {}
    retest_2 = {}
    for c in concepts:
        retest_1[c] = {
            "concept": c,
            "text": f"Retest (Attempt 1): In {concept_names[c]}, what is the correct handling?",
            "options": {
                "a": "Incorrect approach",
                "b": f"Standard verified approach for {concept_names[c]}",
                "c": "Deprecate the component",
                "d": "Bypass validation"
            },
            "correct": "b"
        }
        retest_2[c] = {
            "concept": c,
            "text": f"Retest (Attempt 2): How should an edge-case be resolved in {concept_names[c]}?",
            "options": {
                "a": "Throw an unhandled exception",
                "b": f"Apply canonical {concept_names[c]} remediation",
                "c": "Ignore boundary condition",
                "d": "Restart process"
            },
            "correct": "b"
        }

    return {
        "module_id": slug,
        "title": f"CS3999 — {topic.title()}",
        "description": description or f"Adaptive learning module for {topic.title()}.",
        "concepts": concepts,
        "concept_names": concept_names,
        "available_styles": ["worked_example", "analogy"],
        "default_style": "worked_example",
        "style_descriptions": {
            "worked_example": f"Step-by-step problem walkthrough solving a concrete {topic} scenario.",
            "analogy": f"Intuitive real-world analogy relating {topic} to familiar everyday systems."
        },
        "quiz": quiz,
        "retest_questions": {
            "attempt_1": retest_1,
            "attempt_2": retest_2
        }
    }


def generate_curriculum(
    topic: str,
    description: str = "",
    settings: Settings | None = None,
) -> CurriculumModule:
    """Generate a curriculum module for any topic using OpenRouter or mock fallback."""
    s = settings or get_settings()

    if s.llm_mode != "real":
        mock_data = _generate_mock_module(topic, description)
        return save_module(mock_data)

    # Real LLM call via OpenRouter
    from slice import llm
    from slice.store import Store

    prompt = f"""
You are an expert curriculum designer and university professor.
Create a complete, rigorous, and verified multiple-choice diagnostic quiz and retest bank for the topic: "{topic}".
{f"Context: {description}" if description else ""}

Requirements:
1. Decompose the topic into EXACTLY 4 key sub-concepts (snake_case IDs).
2. Choose EXACTLY 2 pedagogical explanation styles best suited for this subject (e.g. "worked_example", "analogy", "trace", "socratic").
3. Create an 8-question Diagnostic Quiz (EXACTLY 2 questions per concept, IDs Q1 to Q8).
   - 4 options each: "a", "b", "c", "d".
   - Specify the single correct option in "correct" ("a", "b", "c", or "d").
4. Create an Independent Retest Bank:
   - Attempt 1: EXACTLY 1 question per concept (4 total).
   - Attempt 2: EXACTLY 1 variant question per concept (4 total).
   - 4 options each with single correct answer.
5. All questions must test conceptual understanding, not trivial trivia.

Return a JSON object matching this schema:
{{
  "module_id": "short_snake_case_id",
  "title": "Course Code & Topic Title",
  "description": "Brief summary",
  "concepts": ["c1", "c2", "c3", "c4"],
  "concept_names": {{"c1": "Concept 1 Name", ...}},
  "available_styles": ["style1", "style2"],
  "default_style": "style1",
  "style_descriptions": {{"style1": "How this style works for this topic", ...}},
  "quiz": [
    {{"id": "Q1", "concept": "c1", "text": "...", "options": {{"a": "...", "b": "...", "c": "...", "d": "..."}}, "correct": "a"}}, ...
  ],
  "retest_attempt_1": [
    {{"concept": "c1", "text": "...", "options": {{"a": "...", "b": "...", "c": "...", "d": "..."}}, "correct": "b"}}, ...
  ],
  "retest_attempt_2": [
    {{"concept": "c1", "text": "...", "options": {{"a": "...", "b": "...", "c": "...", "d": "..."}}, "correct": "b"}}, ...
  ]
}}
"""

    messages = [
        {"role": "system", "content": "You are a curriculum generation assistant. Return valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    try:
        from slice.budget import Budget
        dummy_store = Store(":memory:")
        run_id = dummy_store.create_run("curriculum_gen")
        budget = Budget(dummy_store, run_id, s)

        result = llm.complete(
            settings=s,
            budget=budget,
            messages=messages,
            schema=GeneratedModuleSchema,
            step="generate_curriculum",
        )

        # Convert GeneratedModuleSchema to CurriculumModule dict format
        module_dict = {
            "module_id": _slugify(result.module_id or topic),
            "title": result.title,
            "description": result.description,
            "concepts": result.concepts,
            "concept_names": result.concept_names,
            "available_styles": result.available_styles,
            "default_style": result.default_style,
            "style_descriptions": result.style_descriptions,
            "quiz": [q.model_dump() for q in result.quiz],
            "retest_questions": {
                "attempt_1": {q.concept: q.model_dump() for q in result.retest_attempt_1},
                "attempt_2": {q.concept: q.model_dump() for q in result.retest_attempt_2},
            }
        }
        return save_module(module_dict)

    except Exception as e:
        print(f"  [Curriculum Generator Warning] Live generation encountered '{type(e).__name__}'. Falling back to template.")
        mock_data = _generate_mock_module(topic, description)
        return save_module(mock_data)
