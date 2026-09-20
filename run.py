#!/usr/bin/env python3
"""
AdaptTutor CLI entrypoint.

Usage:
    python run.py session <student_id> [--module <id>]   Start or resume a remediation session
    python run.py modules                                 List all available course modules
    python run.py generate-curriculum "<topic>"           Generate a new curriculum with AI
    python run.py demo                                   Run deterministic demo with 3 personas
    python run.py replay <run_id>                        Replay a past run's history
    python run.py list                                   List recent runs
    python run.py doctor                                 Run environment diagnostics

Environment:
    LLM_MODE=real      Use OpenRouter LLM (requires OPENROUTER_API_KEY in .env)
"""
from __future__ import annotations

import json
import sys
import os

# Configure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from slice.config import settings as get_settings
from slice.store import Store
from slice.runner import advance
from slice.records import RunState
from remediation.flow import (
    RemediationFlow, start_session, submit_retest,
    score_quiz, get_retest_question, styles_tried_for_concept,
)
from remediation.curriculum import list_modules, get_module, CurriculumModule
from remediation.goals import get_learning_goal, get_goal_achieved
from remediation.practice import (
    get_attempted_question_texts,
    get_next_unused_retest_question,
    get_fresh_retest_question,
    get_guided_practice,
    has_completed_guided_practice,
    get_guided_practice_progress,
    record_guided_practice_event,
)
from remediation.questions import QUIZ_QUESTIONS, ANSWER_KEY, QUESTION_CONCEPT
from remediation.learner import LearnerModel

DB_PATH = os.environ.get("SLICE_DB", "run.db")


# ── Rich UI Card Helpers ───────────────────────────────────────────────────

def mastery_bar(pct: float, width: int = 10) -> str:
    """Render a progress bar like [████████░░]."""
    filled = int(pct / 100 * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


def print_knowledge_gap_card(student_id: str, concept: str, mastery_pct: float,
                              learner: LearnerModel, selected_style: str,
                              reason: str, attempt: int) -> None:
    """Print the adaptive tutor inspection card."""
    eff = learner.style_efficacy
    w = 60
    print(f"\n┌{'─' * w}┐")
    print(f"│ {'🧠 ADAPTIVE TUTOR — KNOWLEDGE GAP DETECTED':<{w}} │")
    print(f"│ {'Concept:':<17}{concept.replace('_', ' ').title():<{w-17}} │")
    print(f"│ {'Current Mastery:':<17}{int(mastery_pct)}% {mastery_bar(mastery_pct):<{w-22}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'Learner History for ' + student_id + ':':<{w}} │")
    if eff:
        for style, data in eff.items():
            pct = int(data["rate"] * 100)
            line = f"  • {style.title()}: {data['wins']}/{data['total']} passed ({pct}%)"
            print(f"│ {line:<{w}} │")
    else:
        print(f"│ {'  • No prior intervention history':<{w}} │")
    print(f"│{' ' * w} │")
    sel_line = f"🎯 Selected Intervention: {selected_style.title()} (Attempt {attempt})"
    print(f"│ {sel_line:<{w}} │")
    reason_line = f"💡 Reason: {reason[:w-11]}"
    print(f"│ {reason_line:<{w}} │")
    print(f"└{'─' * w}┘")


def print_retest_result_card(concept: str, attempt: int, passed: bool,
                              old_mastery: float, new_mastery: float) -> None:
    """Print the retest evaluation card."""
    old_pct = int(old_mastery * 100)
    new_pct = int(new_mastery * 100)
    delta = new_pct - old_pct
    delta_str = f"+{delta}%" if delta >= 0 else f"{delta}%"
    result = "PASSED ✅" if passed else "FAILED ❌"
    w = 60
    print(f"\n┌{'─' * w}┐")
    print(f"│ {'📝 RETEST EVALUATION':<{w}} │")
    line1 = f"Concept: {concept.replace('_', ' ').title()} | Attempt: {attempt}"
    print(f"│ {line1:<{w}} │")
    line2 = f"Result:  {result}"
    print(f"│ {line2:<{w}} │")
    line3 = f"Mastery: {old_pct}% ➔ {new_pct}% {mastery_bar(new_pct)} ({delta_str})"
    print(f"│ {line3:<{w}} │")
    print(f"│ {'Learner Model updated in SQLite.':<{w}} │")
    print(f"└{'─' * w}┘")


def print_adaptation_card(attempt: int, failed_style: str,
                           new_style: str, reason: str) -> None:
    """Print the adaptation-on-failure card."""
    w = 60
    print(f"\n┌{'─' * w}┐")
    print(f"│ {'🔄 ADAPTATION ON FAILURE':<{w}} │")
    line1 = f"Attempt {attempt} ({failed_style.title()}) FAILED."
    print(f"│ {line1:<{w}} │")
    line2 = f"Switching to: {new_style.title()}"
    print(f"│ {line2:<{w}} │")
    line3 = f"Reason: {reason[:w-8]}"
    print(f"│ {line3:<{w}} │")
    print(f"└{'─' * w}┘")


def print_retest_feedback_card(fb: dict) -> None:
    """Print the mistake-specific retest diagnosis card."""
    import textwrap
    w = 60
    opt = fb.get("selected_option", "").upper()
    txt = fb.get("selected_text", "")
    why = fb.get("why_wrong", "")
    rem = fb.get("what_to_remember", "")

    print(f"\n┌{'─' * w}┐")
    print(f"│ {'🔍 RETEST FEEDBACK — MISTAKE DIAGNOSIS':<{w}} │")
    print(f"│{' ' * w} │")
    ans_line = f"Your answer: [{opt}] {txt}"
    for line in textwrap.wrap(ans_line, width=w - 2):
        print(f"│ {line:<{w - 2}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'Why your answer was wrong:':<{w}} │")
    for line in textwrap.wrap(why, width=w - 2):
        print(f"│ {line:<{w - 2}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'What to remember:':<{w}} │")
    for line in textwrap.wrap(rem, width=w - 2):
        print(f"│ {line:<{w - 2}} │")
    print(f"└{'─' * w}┘")


def print_learning_state_card(
    concept: str,
    concept_display: str,
    mastery_pct: int,
    current_style: str,
    attempt: int,
    prev_style: str | None = None,
    prev_failed: bool = False,
    adaptation_reason: str = "",
    goal: str = "",
) -> None:
    """Print the compact learning state and immediate next goal card."""
    import textwrap
    w = 60

    print(f"\n┌{'─' * w}┐")
    print(f"│ {'🎯 YOUR LEARNING STATE':<{w}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'Concept:':<16}{concept_display:<{w - 16}} │")
    mastery_line = f"{mastery_pct}% {mastery_bar(mastery_pct)}"
    print(f"│ {'Mastery:':<16}{mastery_line:<{w - 16}} │")
    print(f"│{' ' * w} │")

    if attempt > 1 and prev_style:
        status_tag = "❌" if prev_failed else "⚠️"
        prev_line = f"Previous approach: {prev_style.replace('_', ' ').title()} {status_tag}"
        print(f"│ {prev_line:<{w}} │")
        print(f"│ {'Result: Did not resolve the gap':<{w}} │")
        print(f"│{' ' * w} │")
        next_line = f"Next approach: {current_style.replace('_', ' ').title()}"
        print(f"│ {next_line:<{w}} │")
        if adaptation_reason:
            reason_line = f"Reason: {adaptation_reason[:w-10]}"
            print(f"│ {reason_line:<{w}} │")
    else:
        curr_line = f"Current approach: {current_style.replace('_', ' ').title()}"
        print(f"│ {curr_line:<{w}} │")

    print(f"│{' ' * w} │")
    print(f"│ {'Current goal:':<{w}} │")
    for line in textwrap.wrap(goal, width=w - 2):
        print(f"│ {line:<{w - 2}} │")
    print(f"└{'─' * w}┘")


def print_concept_improved_card(
    concept_display: str,
    old_mastery: float,
    new_mastery: float,
    goal_achieved: str,
    next_step: str,
) -> None:
    """Print the progress transition card after a successful retest."""
    import textwrap
    w = 60
    old_pct = int(old_mastery * 100)
    new_pct = int(new_mastery * 100)
    delta = new_pct - old_pct
    delta_str = f"+{delta}%" if delta >= 0 else f"{delta}%"

    print(f"\n┌{'─' * w}┐")
    print(f"│ {'✓ CONCEPT IMPROVED':<{w}} │")
    print(f"│{' ' * w} │")
    print(f"│ {concept_display:<{w}} │")
    progress_line = f"{old_pct}% ➔ {new_pct}% {mastery_bar(new_pct)} ({delta_str})"
    print(f"│ {progress_line:<{w}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'Goal achieved:':<{w}} │")
    for line in textwrap.wrap(goal_achieved, width=w - 2):
        print(f"│ {line:<{w - 2}} │")
    print(f"│{' ' * w} │")
    nxt_line = f"Next ➔ {next_step}"
    for line in textwrap.wrap(nxt_line, width=w - 2):
        print(f"│ {line:<{w - 2}} │")
    print(f"└{'─' * w}┘")


def print_escalation_card(student_id: str, concept: str,
                           styles_tried: list[str]) -> None:
    """Print the instructor escalation card."""
    w = 60
    print(f"\n┌{'─' * w}┐")
    print(f"│ {'🚨 ESCALATION TO INSTRUCTOR':<{w}} │")
    line1 = f"Student: {student_id}"
    print(f"│ {line1:<{w}} │")
    line2 = f"Concept: {concept.replace('_', ' ').title()}"
    print(f"│ {line2:<{w}} │")
    line3 = f"Tried: {', '.join(s.title() for s in styles_tried)} — both FAILED"
    print(f"│ {line3:<{w}} │")
    print(f"│ {'Status: Awaiting instructor guidance.':<{w}} │")
    print(f"└{'─' * w}┘")


def print_pool_exhausted_card(concept_display: str) -> None:
    """Print the retest pool exhaustion transition card."""
    w = 60
    print(f"\n┌{'─' * w}┐")
    print(f"│ {'⚠️ RETEST POOL EXHAUSTED':<{w}} │")
    print(f"│{' ' * w} │")
    print(f"│ {f'Concept: {concept_display}':<{w}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'All available retest questions have':<{w}} │")
    print(f"│ {'already been attempted.':<{w}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'Switching to:':<{w}} │")
    print(f"│ {'→ GUIDED PRACTICE':<{w}} │")
    print(f"└{'─' * w}┘\n")


def print_guided_practice_complete_card(concept_display: str) -> None:
    """Print the guided practice completion confirmation card."""
    w = 60
    print(f"\n┌{'─' * w}┐")
    print(f"│ {'✓ GUIDED PRACTICE COMPLETE':<{w}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'You successfully worked through the':<{w}} │")
    print(f"│ {'concept step by step.':<{w}} │")
    print(f"│{' ' * w} │")
    print(f"│ {'Now let\'s test whether you can solve':<{w}} │")
    print(f"│ {'a new problem independently.':<{w}} │")
    print(f"└{'─' * w}┘\n")


def run_guided_practice_session(
    store: Store,
    run_id: str,
    student_id: str,
    concept: str,
    concept_display: str,
    settings,
    topic: str = "",
    interactive: bool = True,
    practice_provider=None,
) -> bool:
    """Run a 3-step Guided Practice session with immediate feedback and retry limits."""
    steps = get_guided_practice(concept, topic=topic, settings=settings)
    progress = get_guided_practice_progress(store, run_id, concept)

    # Resume support: retrieve already completed steps if any
    completed_steps = progress.get("step_results", []) if progress else []
    completed_step_nums = {res.get("step_number") for res in completed_steps}
    step_results = list(completed_steps)

    print(f"\n{'═' * 60}")
    print(f"  🧭 GUIDED PRACTICE: {concept_display.upper()}")
    print("  Let's work through this concept step by step.")
    print(f"{'═' * 60}\n")

    for step in steps:
        if step.step_number in completed_step_nums:
            continue

        w = 60
        print(f"\n┌{'─' * w}┐")
        step_header = f"GUIDED PRACTICE — Step {step.step_number} of {step.total_steps}"
        print(f"│ {step_header:<{w}} │")
        print(f"└{'─' * w}┘")
        if step.context:
            print(f"\n{step.context}")
        print(f"\n{step.prompt}\n")
        for opt, opt_text in step.options.items():
            print(f"  [{opt.upper()}] {opt_text}")

        attempts_on_step = 0
        step_passed = False

        while attempts_on_step < 2:
            attempts_on_step += 1
            if interactive and practice_provider is None:
                while True:
                    ans = input(f"\nYour answer [{'/'.join(step.options.keys())}]: ").strip().lower()
                    if ans in step.options:
                        break
                    print("  Please enter a valid option.")
            elif practice_provider is not None:
                ans = practice_provider(student_id, concept, step.step_number, attempts_on_step)
                if ans is None:
                    ans = step.correct
                print(f"\n  [Practice] Answer: {ans}")
            else:
                ans = step.correct

            if ans == step.correct.lower():
                step_passed = True
                prefix = "✓ Correct!" if attempts_on_step == 1 else "✓ Correct on retry!"
                print(f"\n{prefix} {step.explanation}")
                break
            else:
                if attempts_on_step == 1:
                    print(f"\n❌ Incorrect.")
                    if step.hint:
                        print(f"Hint: {step.hint}")
                    print("Let's try this step one more time.")
                else:
                    correct_opt = step.correct.upper()
                    correct_text = step.options.get(step.correct.lower(), "")
                    print(f"\nCorrection: The correct choice is [{correct_opt}] {correct_text}.")
                    print(f"{step.explanation}")

        step_results.append({
            "step_number": step.step_number,
            "passed": step_passed,
            "attempts": attempts_on_step,
        })
        record_guided_practice_event(
            store=store,
            run_id=run_id,
            student_id=student_id,
            concept=concept,
            completed=False,
            step_results=step_results,
            current_step=step.step_number + 1,
            total_steps=step.total_steps,
        )

    # Mark completely finished
    record_guided_practice_event(
        store=store,
        run_id=run_id,
        student_id=student_id,
        concept=concept,
        completed=True,
        step_results=step_results,
        current_step=len(steps),
        total_steps=len(steps),
    )
    learner = LearnerModel(store, student_id)
    learner.store.record_intervention(student_id, concept, "guided_practice", 0, True)

    print_guided_practice_complete_card(concept_display)
    return True


# ── Session Runner ─────────────────────────────────────────────────────────

def select_topic_menu(student_id: str, store: Store) -> str:
    """Present an interactive course selection menu with learner model mastery."""
    modules = list_modules()
    if not modules:
        return "python_recursion"
    if len(modules) == 1:
        return modules[0]["module_id"]

    learner = LearnerModel(store, student_id)
    profile = learner.profile
    mastery = profile.get("mastery", {})

    print(f"\n{'='*60}")
    print(f"  🎓 AdaptTutor — Course Module Catalog")
    print(f"  Student: {student_id}")
    print(f"{'='*60}\n")
    print("Available Learning Modules:\n")

    recommended_idx = 1
    lowest_mastery = 2.0

    for i, m in enumerate(modules, 1):
        mid = m["module_id"]
        c_list = m.get("concepts", [])
        known = [mastery[c] for c in c_list if c in mastery]
        if known:
            avg_m = sum(known) / len(known)
            avg_pct = int(avg_m * 100)
            status = f"{avg_pct}% {mastery_bar(avg_pct)} " + ("✅ Mastered" if avg_m >= 0.75 else "⚠️ Needs Review")
            if avg_m < lowest_mastery:
                lowest_mastery = avg_m
                recommended_idx = i
        else:
            status = "0% [░░░░░░░░░░] ⏳ Not Started"
            if lowest_mastery == 2.0:
                recommended_idx = i

        print(f"  [{i}] {m['title']}")
        print(f"      Concepts ({m['concept_count']}): {', '.join(c_list[:3])}{'...' if len(c_list) > 3 else ''}")
        print(f"      Your Status: {status}\n")

    print(f"💡 Recommended next module: [{recommended_idx}] {modules[recommended_idx-1]['title']}")
    while True:
        choice = input(f"\nSelect a module [1-{len(modules)}] (default: {recommended_idx}): ").strip()
        if not choice:
            return modules[recommended_idx - 1]["module_id"]
        if choice.isdigit() and 1 <= int(choice) <= len(modules):
            return modules[int(choice) - 1]["module_id"]
        print(f"  Please enter a number between 1 and {len(modules)}.")


def run_session(student_id: str, module_id: str | None = None) -> None:
    """Interactive CLI session for a student."""
    store = Store(DB_PATH)
    s = get_settings()
    flow = RemediationFlow()

    # Check for existing in-progress runs for this student
    existing = None
    existing_mod_id = None
    for run in store.list_runs():
        if run["state"] in (RunState.COMPLETE.value, RunState.FAILED.value):
            continue
        meta = store.meta(run["id"])
        if meta.get("student_id") == student_id:
            existing = run["id"]
            existing_mod_id = meta.get("module_id", "python_recursion")
            break

    if existing:
        ex_mod = get_module(existing_mod_id)
        print(f"\n⚠️ Active in-progress session found: {existing} for '{ex_mod.title}'")
        res = input("Resume this active session? [Y/n]: ").strip().lower()
        if res not in ("n", "no"):
            run_id = existing
            past_experts = store.history(run_id, "expert_answer")
            if past_experts:
                latest_exp = past_experts[-1].payload
                ans = latest_exp.get("answer")
                who = (latest_exp.get("who") or "Instructor").capitalize()
                print(f"\n{'='*60}")
                print(f"📬 LATEST {who.upper()} GUIDANCE")
                print(f"{'='*60}")
                print(f"\"{ans}\"")
                print(f"{'='*60}\n")
        else:
            existing = None

    if not existing:
        chosen_module_id = module_id or select_topic_menu(student_id, store)
        mod = get_module(chosen_module_id)

        print(f"\n{'='*60}")
        print(f"  {mod.title}")
        print(f"  Student: {student_id}")
        print(f"{'='*60}\n")

        answers = {}
        for q in mod.quiz:
            print(f"\n{q.id}. {q.text}")
            for opt, text in q.options.items():
                print(f"  ({opt}) {text}")
            while True:
                ans = input(f"Your answer [{'/'.join(q.options.keys())}]: ").strip().lower()
                if ans in q.options:
                    answers[q.id] = ans
                    break
                print("  Please enter a valid option.")

        run_id = start_session(store, student_id, answers, s, module_id=mod.module_id)
        print(f"\nSession started: {run_id}")

    # Run the state machine
    _drive_session_loop(store, run_id, student_id, s, flow, interactive=True)
    store.close()


def _drive_session_loop(store: Store, run_id: str, student_id: str,
                        s, flow, interactive: bool = True,
                        retest_provider=None,
                        practice_provider=None) -> RunState:
    """Drive the state machine loop with visible adaptation cards.

    If interactive=True, prompts the user for retest answers.
    If retest_provider is a callable, calls it(student_id, concept, style, attempt) for answers.
    If practice_provider is a callable, calls it(student_id, concept, step_num, attempt) for guided practice answers.
    """
    learner = LearnerModel(store, student_id)
    prev_sel = None  # Track previous selection for adaptation cards

    while True:
        state = advance(store, run_id, flow, s)

        if state == RunState.COMPLETE:
            print("\n✅ All concepts resolved. Session complete.")
            # Print final mastery summary
            profile = learner.profile
            if profile["mastery"]:
                print(f"\n{'─'*50}")
                print(f"  Final Mastery for {student_id}:")
                for c, m in profile["mastery"].items():
                    pct = int(m * 100)
                    tag = "✅ STRONG" if m >= 0.75 else ("⚠️ WEAK" if m < 0.60 else "")
                    print(f"    {c.replace('_', ' ').title():<25} {pct}% {mastery_bar(pct)} {tag}")
                print(f"{'─'*50}")
            return state

        elif state == RunState.FAILED:
            print("\n❌ Session ended.")
            return state

        elif state == RunState.AWAITING_EXPERT or state == RunState.PROBING:
            # Determine if waiting for retest (student), guided practice, or instructor
            awaiting_history = store.history(run_id, "awaiting_retest")
            flag_history = store.history(run_id, "instructor_flag")
            gp_history = store.history(run_id, "awaiting_guided_practice")

            latest_awaiting_seq = awaiting_history[-1].seq if awaiting_history else -1
            latest_flag_seq = flag_history[-1].seq if flag_history else -1
            latest_gp_seq = gp_history[-1].seq if gp_history else -1

            if latest_gp_seq > latest_flag_seq and gp_history:
                # ── Guided Practice Triggered (Retest Pool Exhausted) ──
                gp_payload = gp_history[-1].payload
                concept = gp_payload["concept"]
                run_meta = store.meta(run_id)
                mod = get_module(run_meta.get("module_id", "python_recursion"))
                concept_name = mod.concept_display_name(concept)

                # Check if guided practice is already completed (resume support)
                if not has_completed_guided_practice(store, run_id, concept):
                    print_pool_exhausted_card(concept_name)
                    run_guided_practice_session(
                        store=store,
                        run_id=run_id,
                        student_id=student_id,
                        concept=concept,
                        concept_display=concept_name,
                        settings=s,
                        topic=mod.title,
                        interactive=interactive,
                        practice_provider=practice_provider,
                    )

                # ── Fresh Independent Retest ──
                print(f"\n{'─'*50}")
                print(f"🎯 FRESH RETEST: {concept_name}")
                print("Demonstrate your independent understanding.")
                print(f"{'─'*50}\n")

                attempted = get_attempted_question_texts(store, run_id, concept)
                fresh_q = get_fresh_retest_question(mod, concept, attempted, s)
                print(f"Retest: {fresh_q.text}")
                for opt, text in fresh_q.options.items():
                    print(f"  ({opt}) {text}")

                if interactive and retest_provider is None:
                    while True:
                        ans = input(f"Your answer [{'/'.join(fresh_q.options.keys())}]: ").strip().lower()
                        if ans in fresh_q.options:
                            break
                        print("  Please enter a valid option.")
                elif retest_provider is not None:
                    ans = retest_provider(student_id, concept, "fresh_retest", 3)
                    if ans is None:
                        print(f"  [Demo] No answer provided — stopping.")
                        return state
                    print(f"  [Demo] Answer: {ans}")
                else:
                    return state

                passed = ans.strip().lower() == fresh_q.correct.strip().lower()
                old_m = learner.concept_mastery(concept)

                submit_retest(
                    store, run_id, student_id, concept, ans, s,
                    question_text=fresh_q.text, correct_answer=fresh_q.correct,
                )
                store.set_state(run_id, RunState.PROBING)

                # Advance state machine so _evaluate executes
                state = advance(store, run_id, flow, s)
                new_m = learner.concept_mastery(concept)

                if passed:
                    rem_state = store.latest(run_id, "remediation_state")
                    concepts_rem = rem_state.get("concepts_remaining", []) if rem_state else []
                    curr_idx = rem_state.get("current_concept_index", 0) if rem_state else 0
                    if state != RunState.COMPLETE and curr_idx < len(concepts_rem):
                        next_c = concepts_rem[curr_idx]
                        next_step = f"Continue to the next knowledge gap: {mod.concept_display_name(next_c)}"
                    else:
                        next_step = "All concepts resolved! Session complete."

                    goal_achieved = get_goal_achieved(concept, topic=mod.title)
                    print_concept_improved_card(concept_name, old_m, new_m, goal_achieved, next_step)
                else:
                    print_retest_result_card(concept, 3, passed, old_m, new_m)
                    fb = store.latest(run_id, "retest_feedback")
                    if fb:
                        print_retest_feedback_card(fb)

                continue

            elif latest_awaiting_seq > latest_flag_seq and awaiting_history:
                # Need retest answer from student
                sel = store.latest(run_id, "style_selection")
                expl = store.latest(run_id, "explanation")

                if sel and expl:
                    concept = sel["concept"]
                    attempt = sel["attempt"]
                    style = sel["selected_style"]
                    reason = sel.get("reason", "")

                    run_meta = store.meta(run_id)
                    mod = get_module(run_meta.get("module_id", "python_recursion"))
                    concept_name = mod.concept_display_name(concept)
                    current_mastery = learner.concept_mastery(concept)
                    goal = get_learning_goal(concept, topic=mod.title, attempt=attempt)

                    prev_style = prev_sel.get("selected_style") if (attempt > 1 and prev_sel) else None
                    print_learning_state_card(
                        concept=concept,
                        concept_display=concept_name,
                        mastery_pct=int(current_mastery * 100),
                        current_style=style,
                        attempt=attempt,
                        prev_style=prev_style,
                        prev_failed=(attempt > 1),
                        adaptation_reason=reason,
                        goal=goal,
                    )

                    print(f"\n{'─'*50}")
                    print(f"Explanation for: {concept_name}")
                    print(f"Style: {style.title()} (Attempt {attempt})")
                    print(f"{'─'*50}")
                    print(expl["text"])
                    print(f"{'─'*50}\n")

                    # Avoid repeating an already-attempted question
                    attempted_texts = get_attempted_question_texts(store, run_id, concept)
                    retest_q = get_next_unused_retest_question(mod, concept, attempted_texts)
                    if retest_q is None:
                        retest_q = mod.get_retest_question(concept, attempt)

                    print(f"Retest: {retest_q.text}")
                    for opt, text in retest_q.options.items():
                        print(f"  ({opt}) {text}")

                    if interactive and retest_provider is None:
                        while True:
                            ans = input(f"Your answer [{'/'.join(retest_q.options.keys())}]: ").strip().lower()
                            if ans in retest_q.options:
                                break
                            print("  Please enter a valid option.")
                    elif retest_provider is not None:
                        ans = retest_provider(student_id, concept, style, attempt)
                        if ans is None:
                            print(f"  [Demo] No answer provided — stopping.")
                            return state
                        print(f"  [Demo] Answer: {ans}")
                    else:
                        return state

                    # Score the retest
                    passed = ans.strip().lower() == retest_q.correct.strip().lower()
                    old_m = learner.concept_mastery(concept)

                    submit_retest(
                        store, run_id, sel["student_id"], concept, ans, s,
                        question_text=retest_q.text, correct_answer=retest_q.correct,
                    )
                    store.set_state(run_id, RunState.PROBING)

                    # Advance state machine so _evaluate executes, updating learner mastery and state
                    state = advance(store, run_id, flow, s)

                    # Compute new mastery for the card
                    new_m = learner.concept_mastery(concept)

                    if passed:
                        rem_state = store.latest(run_id, "remediation_state")
                        concepts_rem = rem_state.get("concepts_remaining", []) if rem_state else []
                        curr_idx = rem_state.get("current_concept_index", 0) if rem_state else 0
                        if state != RunState.COMPLETE and curr_idx < len(concepts_rem):
                            next_c = concepts_rem[curr_idx]
                            next_step = f"Continue to the next knowledge gap: {mod.concept_display_name(next_c)}"
                        else:
                            next_step = "All concepts resolved! Session complete."

                        goal_achieved = get_goal_achieved(concept, topic=mod.title)
                        print_concept_improved_card(concept_name, old_m, new_m, goal_achieved, next_step)
                    else:
                        print_retest_result_card(concept, attempt, passed, old_m, new_m)
                        fb = store.latest(run_id, "retest_feedback")
                        if fb:
                            print_retest_feedback_card(fb)

                    prev_sel = sel
                    continue
                else:
                    return state
            else:
                # Instructor escalation
                flag = store.latest(run_id, "instructor_flag")
                if flag:
                    print_escalation_card(
                        student_id,
                        flag.get("concept", "unknown"),
                        flag.get("styles_tried", []),
                    )
                print("\nYour instructor has been notified. You will hear back soon.")
                return state
        else:
            return state


# ── Demo Runner ────────────────────────────────────────────────────────────

def run_demo() -> None:
    """Run a live-provider demo with 3 personas showing adaptive behavior.

    Explanation text comes from the real LLM via OpenRouter, so output varies
    with network conditions, model availability, and API credentials.
    Requires OPENROUTER_API_KEY to be set in .env.
    """
    from remediation.stub import get_quiz_answers, get_retest_answer

    os.environ["LLM_MODE"] = "real"

    # Import seed_demo to set up persona histories
    from scripts import seed_demo as seeder

    store = Store(DB_PATH)
    s = get_settings()
    flow = RemediationFlow()

    personas = [
        ("ananya_analogy", "Student A — Has previous success with analogy"),
        ("bharat_trace", "Student B — Has previous failure with analogy, success with trace"),
        ("karthik_stuck", "Student C — Fails both attempts → escalates to instructor"),
    ]

    # Seed the demo histories
    print("\n" + "=" * 60)
    print("  🎓 ADAPT-TUTOR DEMO — 3 Student Personas")
    print("  Same knowledge gap (call_stack), different adaptive paths")
    print("=" * 60)

    seeder.seed_histories(store)

    for student_id, desc in personas:
        print(f"\n\n{'━' * 60}")
        print(f"  {desc}")
        print(f"  Student ID: {student_id}")
        print(f"{'━' * 60}")

        answers = get_quiz_answers(student_id)
        if answers is None:
            print(f"  [Demo] No quiz answers for {student_id}, skipping.")
            continue

        run_id = start_session(store, student_id, answers, s)

        def _answer_fn(sid, concept, style, attempt):
            return get_retest_answer(sid, concept, style, attempt)

        _drive_session_loop(store, run_id, student_id, s, flow,
                           interactive=False, retest_provider=_answer_fn)

    print(f"\n\n{'=' * 60}")
    print("  Demo complete! Visit http://127.0.0.1:8000/students to see the dashboard.")
    print("=" * 60)
    store.close()


# ── Other Commands ─────────────────────────────────────────────────────────

def replay_run(run_id: str) -> None:
    """Replay a past run's history."""
    store = Store(DB_PATH)
    versions = store.replay(run_id)
    if not versions:
        print(f"No history found for run {run_id}")
        return

    print(f"\nReplay of {run_id} ({len(versions)} steps)")
    print("=" * 60)
    for v in versions:
        print(f"\n[{v.seq}] {v.kind} (by {v.produced_by})")
        print(json.dumps(v.payload, indent=2))
    store.close()


def list_runs() -> None:
    """List recent runs."""
    store = Store(DB_PATH)
    runs = store.list_runs()
    if not runs:
        print("No runs found.")
        return

    print(f"\n{'ID':<30} {'State':<20} {'Domain'}")
    print("-" * 70)
    for r in runs:
        print(f"{r['id']:<30} {r['state']:<20} {r['domain']}")
    store.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "session" and len(sys.argv) >= 3:
        student_id = sys.argv[2]
        module_id = None
        if "--module" in sys.argv:
            idx = sys.argv.index("--module")
            if idx + 1 < len(sys.argv):
                module_id = sys.argv[idx + 1]
        elif "-m" in sys.argv:
            idx = sys.argv.index("-m")
            if idx + 1 < len(sys.argv):
                module_id = sys.argv[idx + 1]
        run_session(student_id, module_id=module_id)
    elif cmd == "modules":
        mods = list_modules()
        print(f"\n{'ID':<25} {'Concepts':<10} {'Title'}")
        print("─" * 70)
        for m in mods:
            print(f"{m['module_id']:<25} {m['concept_count']:<10} {m['title']}")
        print()
    elif cmd == "generate-curriculum" and len(sys.argv) >= 3:
        topic = sys.argv[2]
        desc = sys.argv[3] if len(sys.argv) >= 4 else ""
        from remediation.curriculum_generator import generate_curriculum
        print(f"\n[AdaptTutor] Generating curriculum for topic: '{topic}'...")
        mod = generate_curriculum(topic, description=desc)
        print(f"\n✅ Curriculum Module Created Successfully!")
        print(f"  Module ID: {mod.module_id}")
        print(f"  Title:     {mod.title}")
        print(f"  Concepts:  {', '.join(mod.concepts)}")
        print(f"  Styles:    {', '.join(mod.available_styles)}")
        print(f"  Questions: {len(mod.quiz)} diagnostic questions + {len(mod.retest_attempt_1)} retests")
        print(f"\nStudents can now take this module via:")
        print(f"  python run.py session <student_id> --module {mod.module_id}\n")
    elif cmd == "demo":
        run_demo()
    elif cmd == "replay" and len(sys.argv) >= 3:
        replay_run(sys.argv[2])
    elif cmd == "list":
        list_runs()
    elif cmd == "doctor":
        import subprocess
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "scripts", "doctor.py")])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
