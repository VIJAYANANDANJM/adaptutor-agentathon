"""
Curriculum module registry and loader.

Supports multiple topic modules (e.g., python_recursion, db_normalization)
stored as validated JSON packages in data/modules/.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from remediation.questions import QuizQuestion, RetestQuestion

MODULES_DIR = Path(__file__).parent.parent / "data" / "modules"
DEFAULT_MODULE_ID = "python_recursion"


@dataclass
class CurriculumModule:
    module_id: str
    title: str
    description: str
    concepts: list[str]
    concept_names: dict[str, str]
    available_styles: list[str]
    default_style: str
    style_descriptions: dict[str, str]
    quiz: list[QuizQuestion]
    retest_attempt_1: dict[str, RetestQuestion]
    retest_attempt_2: dict[str, RetestQuestion]

    # Cached lookups
    _answer_key: dict[str, str] = field(init=False, default_factory=dict)
    _question_concept: dict[str, str] = field(init=False, default_factory=dict)
    _question_by_id: dict[str, QuizQuestion] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self._answer_key = {q.id: q.correct for q in self.quiz}
        self._question_concept = {q.id: q.concept for q in self.quiz}
        self._question_by_id = {q.id: q for q in self.quiz}

    @property
    def answer_key(self) -> dict[str, str]:
        return self._answer_key

    @property
    def question_concept(self) -> dict[str, str]:
        return self._question_concept

    @property
    def question_by_id(self) -> dict[str, QuizQuestion]:
        return self._question_by_id

    def get_retest_question(self, concept: str, attempt: int) -> RetestQuestion:
        if attempt <= 1:
            return self.retest_attempt_1.get(
                concept,
                RetestQuestion(concept, f"Default retest question for {concept}", {"a": "True", "b": "False"}, "a")
            )
        return self.retest_attempt_2.get(
            concept,
            RetestQuestion(concept, f"Default variant retest question for {concept}", {"a": "True", "b": "False"}, "a")
        )

    def concept_display_name(self, concept: str) -> str:
        return self.concept_names.get(concept, concept.replace("_", " ").title())


# In-memory module cache
_MODULE_CACHE: dict[str, CurriculumModule] = {}


def _parse_module_dict(data: dict[str, Any]) -> CurriculumModule:
    quiz_questions = [
        QuizQuestion(
            id=item["id"],
            concept=item["concept"],
            text=item["text"],
            options=item["options"],
            correct=item["correct"],
        )
        for item in data.get("quiz", [])
    ]

    retest_raw = data.get("retest_questions", {})
    retest_1 = {
        c: RetestQuestion(
            concept=q["concept"],
            text=q["text"],
            options=q["options"],
            correct=q["correct"],
        )
        for c, q in retest_raw.get("attempt_1", {}).items()
    }
    retest_2 = {
        c: RetestQuestion(
            concept=q["concept"],
            text=q["text"],
            options=q["options"],
            correct=q["correct"],
        )
        for c, q in retest_raw.get("attempt_2", {}).items()
    }

    return CurriculumModule(
        module_id=data["module_id"],
        title=data.get("title", data["module_id"]),
        description=data.get("description", ""),
        concepts=data.get("concepts", []),
        concept_names=data.get("concept_names", {}),
        available_styles=data.get("available_styles", ["analogy", "trace"]),
        default_style=data.get("default_style", "analogy"),
        style_descriptions=data.get("style_descriptions", {}),
        quiz=quiz_questions,
        retest_attempt_1=retest_1,
        retest_attempt_2=retest_2,
    )


def get_module(module_id: str | None = None) -> CurriculumModule:
    """Get a curriculum module by ID. Defaults to python_recursion."""
    mid = module_id or DEFAULT_MODULE_ID
    if mid in _MODULE_CACHE:
        return _MODULE_CACHE[mid]

    module_file = MODULES_DIR / f"{mid}.json"
    if not module_file.exists():
        # Fallback to default if requested module file doesn't exist
        default_file = MODULES_DIR / f"{DEFAULT_MODULE_ID}.json"
        if default_file.exists():
            with open(default_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            mod = _parse_module_dict(data)
            _MODULE_CACHE[DEFAULT_MODULE_ID] = mod
            return mod
        raise FileNotFoundError(f"Module file not found: {module_file}")

    with open(module_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    mod = _parse_module_dict(data)
    _MODULE_CACHE[mid] = mod
    return mod


def list_modules() -> list[dict[str, Any]]:
    """List all available curriculum modules from data/modules/."""
    if not MODULES_DIR.exists():
        return []

    modules = []
    for p in sorted(MODULES_DIR.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            modules.append({
                "module_id": data.get("module_id", p.stem),
                "title": data.get("title", p.stem.replace("_", " ").title()),
                "description": data.get("description", ""),
                "concepts": data.get("concepts", []),
                "concept_count": len(data.get("concepts", [])),
                "available_styles": data.get("available_styles", []),
                "default_style": data.get("default_style", "analogy"),
            })
        except Exception:
            continue
    return modules


def save_module(module_data: dict[str, Any]) -> CurriculumModule:
    """Validate and write a new curriculum module to data/modules/<module_id>.json."""
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    mid = module_data.get("module_id")
    if not mid:
        raise ValueError("module_data must contain 'module_id'")

    # Validate by parsing into CurriculumModule
    mod = _parse_module_dict(module_data)

    target_path = MODULES_DIR / f"{mid}.json"
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(module_data, f, indent=2)

    _MODULE_CACHE[mid] = mod
    return mod
