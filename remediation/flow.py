"""
State machine handlers for the remediation loop.

QUIZ -> DIAGNOSE -> SELECT -> EXPLAIN -> RETEST -> EVALUATE
                     ▲                                │
                     └────── (failed, other style ────┘
                              available)
                                                      │
                                    (both failed) ────┘
                                                      ▼
                                          WAITING_INSTRUCTOR
                                               │          │
                                  (responded) ─┘          └─ (timeout)
                                      ▼                        ▼
                                   RESOLVED          CLOSED_UNRESOLVED

Deterministic code handles: scoring, concept mapping, style selection,
retest scoring, revision tracking, and instructor escalation.
The LLM is used ONLY for generating explanation text.
"""
from __future__ import annotations

from typing import Any, Callable

from slice import callback
from slice.budget import Budget
from slice.config import Settings
from slice.records import RunState
from slice.runner import Context, Handler
from slice.store import Store

from remediation.learner import LearnerModel
from remediation.provider import ExplanationProvider, get_provider
from remediation.questions import (
    ANSWER_KEY, ALL_CONCEPTS, QUESTION_BY_ID, QUESTION_CONCEPT,
    RETEST_QUESTIONS, get_retest_question,
)
from remediation.schema import (
    Diagnosis, ExplanationPayload, InstructorFlag, Outcome,
    QuizSubmission, RetestResult, StyleSelection,
)
from remediation.selector import adaptive_select

MAX_REVISIONS_PER_CONCEPT = 2
STYLES = ["analogy", "trace"]
DEFAULT_STYLE = "analogy"


# ── Deterministic: Score quiz answers ──────────────────────────────────────

def score_quiz(answers: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """Score answers against the fixed key. Returns (wrong_questions, failed_concepts, passed_concepts)."""
    wrong = [qid for qid, ans in answers.items() if ANSWER_KEY.get(qid) != ans.strip().lower()]
    failed_concepts = list(dict.fromkeys(QUESTION_CONCEPT[q] for q in wrong))
    all_tested = list(dict.fromkeys(QUESTION_CONCEPT[q] for q in answers))
    passed = [c for c in all_tested if c not in failed_concepts]
    return wrong, failed_concepts, passed


# ── Deterministic: Adaptive style selection ────────────────────────────────

def select_style(store: Store, student_id: str, concept: str,
                 styles_tried: list[str]) -> tuple[str, str]:
    """Pick the best explanation style for a concept.

    Delegates to remediation.selector.adaptive_select which uses:
        Score(style) = 0.7 × StudentRate + 0.3 × CohortRate

    Returns (selected_style, reason).
    """
    return adaptive_select(store, student_id, concept, styles_tried)


# ── Deterministic: Count revisions for a concept ──────────────────────────

def count_revisions(store: Store, run_id: str, concept: str) -> int:
    """Count style_selection records for a specific concept in this run."""
    selections = store.history(run_id, "style_selection")
    return sum(1 for v in selections if v.payload.get("concept") == concept)


def styles_tried_for_concept(store: Store, run_id: str, concept: str) -> list[str]:
    """Which styles have been tried for a concept in this run."""
    selections = store.history(run_id, "style_selection")
    return [v.payload["selected_style"] for v in selections
            if v.payload.get("concept") == concept]


# ── State machine handlers ─────────────────────────────────────────────────

def handle_quiz(ctx: Context) -> RunState:
    """QUIZ -> DIAGNOSE: Read the quiz submission and score it.
    Also initializes the persistent learner model from quiz results."""
    sub = ctx.latest("quiz_submission")
    if sub is None:
        return RunState.FAILED

    answers = sub["answers"]
    student_id = sub["student_id"]

    wrong, failed, passed = score_quiz(answers)

    diag = Diagnosis(
        student_id=student_id,
        wrong_questions=wrong,
        concepts_failed=failed,
        concepts_passed=passed,
    )
    ctx.append("diagnosis", diag.model_dump(), produced_by="system")

    # ── Initialize persistent learner model from quiz ──
    learner = LearnerModel(ctx.store, student_id)
    learner.init_from_quiz(passed, failed)

    if not failed:
        ctx.append("outcome", {
            "kind": "outcome",
            "student_id": student_id,
            "concept": "all",
            "style": "none",
            "passed": True,
            "total_attempts": 0,
        }, produced_by="system")
        return RunState.COMPLETE

    # Store current concept index to process
    ctx.append("remediation_state", {
        "student_id": student_id,
        "concepts_remaining": failed,
        "current_concept_index": 0,
    }, produced_by="system")

    return RunState.GATING  # GATING = SELECT step


def handle_select(ctx: Context) -> RunState:
    """SELECT -> EXPLAIN: Pick the best explanation style for current concept."""
    rem_state = ctx.latest("remediation_state")
    if rem_state is None:
        return RunState.FAILED

    student_id = rem_state["student_id"]
    concepts = rem_state["concepts_remaining"]
    idx = rem_state["current_concept_index"]

    if idx >= len(concepts):
        return RunState.COMPLETE

    concept = concepts[idx]
    tried = styles_tried_for_concept(ctx.store, ctx.run_id, concept)
    revisions = len(tried)

    if revisions >= MAX_REVISIONS_PER_CONCEPT:
        flag = InstructorFlag(
            student_id=student_id,
            concept=concept,
            styles_tried=tried,
            both_failed=True,
            state="waiting_instructor",
            message=(
                f"{student_id} could not demonstrate understanding of "
                f"{concept.replace('_', ' ')} after two explanation attempts. "
                f"Needs instructor."
            ),
        )
        ctx.append("instructor_flag", flag.model_dump(), produced_by="system")

        callback.ask(
            ctx.store, ctx.run_id,
            question=flag.message,
            context={
                "student_id": student_id,
                "concept": concept,
                "styles_tried": tried,
                "resume_state": RunState.PROBING.value,
            },
            settings=ctx.settings,
        )
        return RunState.AWAITING_EXPERT

    selected, reason = select_style(ctx.store, student_id, concept, tried)
    attempt = revisions + 1

    sel = StyleSelection(
        student_id=student_id,
        concept=concept,
        selected_style=selected,
        reason=reason,
        attempt=attempt,
    )
    ctx.append("style_selection", sel.model_dump(), produced_by="system")

    return RunState.DRAFTING  # DRAFTING = EXPLAIN step


def handle_explain(ctx: Context) -> RunState:
    """EXPLAIN -> RETEST: Generate explanation using selected provider."""
    sel_data = ctx.latest("style_selection")
    if sel_data is None:
        return RunState.FAILED

    student_id = sel_data["student_id"]
    concept = sel_data["concept"]
    style = sel_data["selected_style"]
    attempt = sel_data.get("attempt", 1)

    sub = ctx.latest("quiz_submission")
    q_answers = sub["answers"] if sub else {}

    wrong_questions = [qid for qid in q_answers
                       if QUESTION_CONCEPT.get(qid) == concept
                       and ANSWER_KEY.get(qid) != q_answers[qid].strip().lower()]

    if wrong_questions:
        qid = wrong_questions[0]
        q = QUESTION_BY_ID.get(qid)
        question_text = q.text if q else ""
        wrong_answer = q_answers.get(qid, "")
        correct_answer = ANSWER_KEY.get(qid, "")
        options = q.options if q else {}
    else:
        question_text, wrong_answer, correct_answer = "", "", ""
        options = {}

    # Extract LearnerModel concept mastery
    learner = LearnerModel(ctx.store, student_id)
    mastery_pct = int(learner.concept_mastery(concept) * 100)

    # Extract styles tried for this concept
    tried = styles_tried_for_concept(ctx.store, ctx.run_id, concept)
    prev_styles = [s for s in tried if s != style]

    provider = get_provider()
    print(f"\n[AI Tutor] Generating {style} explanation for {concept.replace('_', ' ').title()} (waiting for model response)...")
    explanation = provider.explain(
        student_id=student_id,
        concept=concept,
        style=style,
        wrong_answer=wrong_answer,
        correct_answer=correct_answer,
        question_text=question_text,
        budget=ctx.budget,
        settings=ctx.settings,
        options=options,
        attempt=attempt,
        mastery_pct=mastery_pct,
        previous_styles=prev_styles,
    )

    ctx.append("explanation", explanation.model_dump(), produced_by="llm")

    # Budget: count this as a model call
    ctx.store.bump(ctx.run_id, "model_calls")

    return RunState.PROBING  # PROBING = RETEST step



def handle_retest(ctx: Context) -> RunState:
    """RETEST -> EVALUATE: Check if a retest result has been submitted.

    Also handles return from instructor suspension: if an expert_answer
    exists for the current concept after both styles were exhausted,
    resolve the concept based on the instructor's response.
    """
    sel = ctx.latest("style_selection")
    if sel is None:
        return RunState.FAILED

    concept = sel["concept"]
    attempt = sel["attempt"]
    student_id = sel["student_id"]

    # Check if we're returning from instructor escalation
    flag_history = ctx.history("instructor_flag")
    expert_history = ctx.history("expert_answer")
    concept_flags = [f for f in flag_history if f.payload.get("concept") == concept]

    if concept_flags:
        last_flag_seq = concept_flags[-1].seq
        # Look for expert answers that came after the flag
        post_flag_answers = [e for e in expert_history if e.seq > last_flag_seq]

        if post_flag_answers:
            latest_expert = post_flag_answers[-1].payload
            source = latest_expert.get("source", "")

            rem_state = ctx.latest("remediation_state")
            if rem_state is None:
                return RunState.FAILED

            concepts = rem_state["concepts_remaining"]
            idx = rem_state["current_concept_index"]

            if source == "unresolved_no_expert":
                print(f"\n{'='*60}")
                print(f"⚠️ NO INSTRUCTOR RESPONSE FOR: {concept.replace('_', ' ').title()}")
                print(f"Status: Flag timed out without human response. Concept marked unresolved.")
                print(f"{'='*60}\n")
                ctx.append("outcome", Outcome(
                    student_id=student_id,
                    concept=concept,
                    style="instructor",
                    passed=False,
                    total_attempts=MAX_REVISIONS_PER_CONCEPT,
                ).model_dump(), produced_by="system")

                next_idx = idx + 1
                if next_idx >= len(concepts):
                    return RunState.FAILED

                ctx.append("remediation_state", {
                    "student_id": student_id,
                    "concepts_remaining": concepts,
                    "current_concept_index": next_idx,
                }, produced_by="system")
                return RunState.GATING
            else:
                # Instructor responded with a hint — mark concept resolved
                instructor_msg = latest_expert.get("answer", "")
                who = (latest_expert.get("who") or "Instructor").capitalize()
                print(f"\n{'='*60}")
                print(f"📬 {who.upper()} GUIDANCE RECEIVED FOR: {concept.replace('_', ' ').title()}")
                print(f"{'='*60}")
                print(f"Instructor feedback: \"{instructor_msg}\"")
                print(f"Status: Concept '{concept.replace('_', ' ').title()}' resolved via instructor intervention.")
                print(f"{'='*60}\n")

                # Update learner model for instructor resolution
                learner = LearnerModel(ctx.store, student_id)
                learner.update_on_instructor(concept)

                ctx.append("outcome", Outcome(
                    student_id=student_id,
                    concept=concept,
                    style="instructor",
                    passed=True,
                    total_attempts=MAX_REVISIONS_PER_CONCEPT,
                ).model_dump(), produced_by="system")

                next_idx = idx + 1
                if next_idx >= len(concepts):
                    return RunState.COMPLETE

                next_concept = concepts[next_idx]
                print(f"Moving to next concept needing remediation: {next_concept.replace('_', ' ').title()}...\n")

                ctx.append("remediation_state", {
                    "student_id": student_id,
                    "concepts_remaining": concepts,
                    "current_concept_index": next_idx,
                }, produced_by="system")
                return RunState.GATING

    # Normal retest flow: find a retest result matching this concept+attempt
    retests = ctx.history("retest_result")
    matching = [v for v in retests
                if v.payload.get("concept") == concept
                and v.payload.get("attempt") == attempt]

    if not matching:
        # No retest submitted yet — mark as waiting for student input
        ctx.append("awaiting_retest", {
            "concept": concept,
            "attempt": attempt,
            "student_id": student_id,
            "style": sel["selected_style"],
        }, produced_by="system")
        return RunState.AWAITING_EXPERT  # Suspend until retest submitted

    # Use the latest matching retest
    retest = matching[-1].payload
    return _evaluate(ctx, retest, sel)


def _evaluate(ctx: Context, retest: dict, sel: dict) -> RunState:
    """EVALUATE: Score retest. Pass → RESOLVED. Fail + untried → backward. Fail + both → flag.
    Updates the persistent learner model after evaluation."""
    student_id = retest["student_id"]
    concept = retest["concept"]
    style = retest["style_used"]
    passed = retest["passed"]
    attempt = retest["attempt"]

    # ── Update persistent learner model ──
    learner = LearnerModel(ctx.store, student_id)
    learner.update_on_retest(concept, style, attempt, passed)

    outcome = Outcome(
        student_id=student_id,
        concept=concept,
        style=style,
        passed=passed,
        total_attempts=attempt,
    )
    ctx.append("outcome", outcome.model_dump(), produced_by="system")

    rem_state = ctx.latest("remediation_state")
    if rem_state is None:
        return RunState.FAILED

    concepts = rem_state["concepts_remaining"]
    idx = rem_state["current_concept_index"]

    if passed:
        next_idx = idx + 1
        if next_idx >= len(concepts):
            return RunState.COMPLETE

        ctx.append("remediation_state", {
            "student_id": student_id,
            "concepts_remaining": concepts,
            "current_concept_index": next_idx,
        }, produced_by="system")
        return RunState.GATING  # back to SELECT for next concept

    tried = styles_tried_for_concept(ctx.store, ctx.run_id, concept)
    untried = [s for s in STYLES if s not in tried]

    if untried:
        # Backward loop: return to SELECT to try another style
        return RunState.GATING

    # Both styles failed: escalate to instructor with enriched context
    learner = LearnerModel(ctx.store, student_id)
    mastery_pct = int(learner.concept_mastery(concept) * 100)
    budget_info = ctx.budget.summary()

    # Collect wrong answers for this concept
    sub = ctx.latest("quiz_submission")
    q_answers = sub["answers"] if sub else {}
    wrong_answers = {}
    for qid, ans in q_answers.items():
        if QUESTION_CONCEPT.get(qid) == concept and ANSWER_KEY.get(qid) != ans.strip().lower():
            wrong_answers[qid] = ans

    flag = InstructorFlag(
        student_id=student_id,
        concept=concept,
        styles_tried=tried,
        both_failed=True,
        state="waiting_instructor",
        message=(
            f"{student_id} could not demonstrate understanding of "
            f"{concept.replace('_', ' ')} after two explanation attempts. "
            f"Needs instructor."
        ),
    )
    ctx.append("instructor_flag", flag.model_dump(), produced_by="system")

    callback.ask(
        ctx.store, ctx.run_id,
        question=flag.message,
        context={
            "student_id": student_id,
            "concept": concept,
            "styles_tried": tried,
            "mastery_pct": mastery_pct,
            "wrong_answers": wrong_answers,
            "budget_remaining": budget_info["tokens_remaining"],
            "resume_state": RunState.PROBING.value,
        },
        settings=ctx.settings,
    )
    return RunState.AWAITING_EXPERT


def handle_instructor_response(ctx: Context) -> RunState:
    """Handle return from AWAITING_EXPERT. Check if instructor responded or timed out."""
    expert = ctx.latest("expert_answer")
    if expert is None:
        return RunState.PROBING

    source = expert.get("source", "")
    concept_context = expert.get("concept")

    rem_state = ctx.latest("remediation_state")
    if rem_state is None:
        return RunState.FAILED

    student_id = rem_state["student_id"]
    concepts = rem_state["concepts_remaining"]
    idx = rem_state["current_concept_index"]
    concept = concepts[idx] if idx < len(concepts) else None

    if source == "unresolved_no_expert":
        if concept:
            ctx.append("outcome", Outcome(
                student_id=student_id,
                concept=concept,
                style="instructor",
                passed=False,
                total_attempts=MAX_REVISIONS_PER_CONCEPT,
            ).model_dump(), produced_by="system")

        next_idx = idx + 1
        if next_idx >= len(concepts):
            return RunState.FAILED
        ctx.append("remediation_state", {
            "student_id": student_id,
            "concepts_remaining": concepts,
            "current_concept_index": next_idx,
        }, produced_by="system")
        return RunState.GATING

    # Instructor responded with a hint. Mark concept resolved.
    if concept:
        learner = LearnerModel(ctx.store, student_id)
        learner.update_on_instructor(concept)

        ctx.append("outcome", Outcome(
            student_id=student_id,
            concept=concept,
            style="instructor",
            passed=True,
            total_attempts=MAX_REVISIONS_PER_CONCEPT,
        ).model_dump(), produced_by="system")

    next_idx = idx + 1
    if next_idx >= len(concepts):
        return RunState.COMPLETE
    ctx.append("remediation_state", {
        "student_id": student_id,
        "concepts_remaining": concepts,
        "current_concept_index": next_idx,
    }, produced_by="system")
    return RunState.GATING


# ── Flow registration ──────────────────────────────────────────────────────

class RemediationFlow:
    """The AdaptTutor remediation flow. Maps RunState to handlers.

    State mapping to domain steps:
        DRAFTING  = EXPLAIN (generate explanation)
        GATING    = SELECT (pick style)
        PROBING   = RETEST/EVALUATE (administer & score retest)

    Terminal: COMPLETE, FAILED
    Suspended: AWAITING_EXPERT
    """
    name = "remediation"
    handlers: dict[RunState, Handler] = {
        RunState.DRAFTING: handle_explain,
        RunState.GATING: handle_select,
        RunState.PROBING: handle_retest,
    }


# ── High-level orchestration for programmatic use ──────────────────────────

def start_session(store: Store, student_id: str, answers: dict[str, str],
                  settings: Settings) -> str:
    """Start a new remediation session: create run, submit quiz, run through QUIZ."""
    run_id = store.create_run("remediation", meta={"student_id": student_id})

    sub = QuizSubmission(student_id=student_id, answers=answers)
    store.append(run_id, "quiz_submission", sub.model_dump(), produced_by="student")

    # Run the quiz handler directly to transition from DRAFTING
    from slice.runner import Context as Ctx
    ctx = Ctx(store, run_id, settings)
    next_state = handle_quiz(ctx)
    store.set_state(run_id, next_state)

    return run_id


def submit_retest(store: Store, run_id: str, student_id: str, concept: str,
                  answer: str, settings: Settings) -> None:
    """Submit a student's retest answer and score it deterministically."""
    selections = store.history(run_id, "style_selection")
    relevant = [v for v in selections if v.payload.get("concept") == concept]
    if not relevant:
        return

    latest_sel = relevant[-1]
    style = latest_sel.payload["selected_style"]
    attempt = latest_sel.payload["attempt"]

    retest_q = get_retest_question(concept, attempt)
    passed = answer.strip().lower() == retest_q.correct.strip().lower()

    result = RetestResult(
        student_id=student_id,
        concept=concept,
        style_used=style,
        attempt=attempt,
        passed=passed,
        student_answer=answer,
        correct_answer=retest_q.correct,
    )
    store.append(run_id, "retest_result", result.model_dump(), produced_by="student")
