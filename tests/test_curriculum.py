"""
Tests for topic-agnostic multi-module curriculum and AI curriculum generator.
"""
import os
from unittest.mock import patch
import pytest

os.environ.setdefault("LLM_MODE", "real")

from slice.config import settings as get_settings
from slice.records import RunState
from slice.runner import advance
from slice.store import Store

from remediation.curriculum import list_modules, get_module, CurriculumModule
from remediation.curriculum_generator import generate_curriculum
from remediation.flow import RemediationFlow, start_session, submit_retest, score_quiz
from remediation.learner import LearnerModel
from remediation.schema import ExplanationPayload


@pytest.fixture(autouse=True)
def fake_llm_completion():
    with patch("slice.llm.complete") as m:
        def _fake_complete(*args, **kwargs):
            step = kwargs.get("step", "")
            style = "worked_example" if "worked_example" in step else "analogy"
            concept = "first_normal_form"
            return ExplanationPayload(
                student_id="student",
                concept=concept,
                style=style,
                text=f"Explanation for {concept} using {style}."
            )
        m.side_effect = _fake_complete
        yield m


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test_curriculum.db"))


def test_list_modules():
    modules = list_modules()
    ids = [m["module_id"] for m in modules]
    assert "python_recursion" in ids
    assert "db_normalization" in ids


def test_get_module_default():
    mod = get_module()
    assert mod.module_id == "python_recursion"
    assert "base_case" in mod.concepts
    assert len(mod.quiz) == 8


def test_get_module_db_normalization():
    mod = get_module("db_normalization")
    assert mod.module_id == "db_normalization"
    assert "first_normal_form" in mod.concepts
    assert "worked_example" in mod.available_styles
    assert mod.default_style == "worked_example"
    assert len(mod.quiz) == 8
    assert len(mod.retest_attempt_1) == 4


def test_score_quiz_with_module():
    # Scoring for db_normalization
    answers = {
        "Q1": "b",  # correct
        "Q2": "a",  # wrong (correct is b)
        "Q3": "a",  # correct
        "Q4": "b",  # correct
        "Q5": "a",  # correct
        "Q6": "b",  # correct
        "Q7": "a",  # correct
        "Q8": "a",  # correct
    }
    wrong, failed, passed = score_quiz(answers, module_id="db_normalization")
    assert wrong == ["Q2"]
    assert failed == ["first_normal_form"]
    assert "second_normal_form" in passed


def test_curriculum_generator_mock(tmp_path):
    s = get_settings()
    mod = generate_curriculum("Operating Systems Virtual Memory", settings=s)
    assert mod.module_id.startswith("operating_systems_virtual")
    assert len(mod.concepts) == 4
    assert len(mod.quiz) == 8
    assert len(mod.retest_attempt_1) == 4
    assert len(mod.retest_attempt_2) == 4


def test_multi_module_session_e2e(store):
    """Run an end-to-end session on the db_normalization module."""
    s = get_settings()
    flow = RemediationFlow()
    student_id = "student_db_test"

    # Student misses Q1 and Q2 (first_normal_form)
    answers = {
        "Q1": "a",  # wrong (correct is b)
        "Q2": "a",  # wrong (correct is b)
        "Q3": "a",
        "Q4": "b",
        "Q5": "a",
        "Q6": "b",
        "Q7": "a",
        "Q8": "a",
    }

    run_id = start_session(store, student_id, answers, s, module_id="db_normalization")
    assert store.meta(run_id)["module_id"] == "db_normalization"

    # Step through: GATING (style selection) -> DRAFTING (explain) -> PROBING (awaiting retest)
    state = advance(store, run_id, flow, s)
    assert state in (RunState.PROBING, RunState.AWAITING_EXPERT)

    sel = store.latest(run_id, "style_selection")
    assert sel is not None
    assert sel["concept"] == "first_normal_form"
    # The selected style must be one of db_normalization's available styles
    assert sel["selected_style"] in ["worked_example", "analogy"]

    # Student passes the retest for first_normal_form
    mod = get_module("db_normalization")
    retest_q = mod.get_retest_question("first_normal_form", 1)
    submit_retest(store, run_id, student_id, "first_normal_form", retest_q.correct, s)

    # Resume to evaluate
    store.set_state(run_id, RunState.PROBING)
    final_state = advance(store, run_id, flow, s)
    assert final_state == RunState.COMPLETE

    # Check LearnerModel
    learner = LearnerModel(store, student_id)
    assert learner.concept_mastery("first_normal_form") >= 0.70
    assert "first_normal_form" not in learner.weak_concepts
