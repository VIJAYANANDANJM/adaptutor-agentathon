#!/usr/bin/env python3
"""
AdaptTutor CLI entrypoint.

Usage:
    python run.py session <student_id>      Start or resume a remediation session
    python run.py demo                      Run deterministic demo with 3 personas
    python run.py replay <run_id>           Replay a past run's history
    python run.py list                      List recent runs
    python run.py doctor                    Run environment diagnostics

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


# ── Session Runner ─────────────────────────────────────────────────────────

def run_session(student_id: str) -> None:
    """Interactive CLI session for a student."""
    store = Store(DB_PATH)
    s = get_settings()
    flow = RemediationFlow()

    # Check for existing in-progress runs for this student
    existing = None
    for run in store.list_runs():
        if run["state"] in (RunState.COMPLETE.value, RunState.FAILED.value):
            continue
        meta = store.meta(run["id"])
        if meta.get("student_id") == student_id:
            existing = run["id"]
            break

    if existing:
        print(f"Resuming session {existing} for {student_id}...")
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
        print(f"\n{'='*60}")
        print(f"  CS3301 Data Structures — Week 6 Recursion Quiz")
        print(f"  Student: {student_id}")
        print(f"{'='*60}\n")

        answers = {}
        for q in QUIZ_QUESTIONS:
            print(f"\n{q.id}. {q.text}")
            for opt, text in q.options.items():
                print(f"  ({opt}) {text}")
            while True:
                ans = input(f"Your answer [{'/'.join(q.options.keys())}]: ").strip().lower()
                if ans in q.options:
                    answers[q.id] = ans
                    break
                print("  Please enter a valid option.")

        run_id = start_session(store, student_id, answers, s)
        print(f"\nSession started: {run_id}")

    # Run the state machine
    _drive_session_loop(store, run_id, student_id, s, flow, interactive=True)
    store.close()


def _drive_session_loop(store: Store, run_id: str, student_id: str,
                        s, flow, interactive: bool = True,
                        retest_provider=None) -> RunState:
    """Drive the state machine loop with visible adaptation cards.

    If interactive=True, prompts the user for retest answers.
    If retest_provider is a callable, calls it(student_id, concept, style, attempt) for answers.
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
            # Determine if waiting for retest (student) or instructor
            awaiting_history = store.history(run_id, "awaiting_retest")
            flag_history = store.history(run_id, "instructor_flag")

            latest_awaiting_seq = awaiting_history[-1].seq if awaiting_history else -1
            latest_flag_seq = flag_history[-1].seq if flag_history else -1

            if latest_awaiting_seq > latest_flag_seq and awaiting_history:
                # Need retest answer from student
                sel = store.latest(run_id, "style_selection")
                expl = store.latest(run_id, "explanation")

                if sel and expl:
                    concept = sel["concept"]
                    attempt = sel["attempt"]
                    style = sel["selected_style"]
                    reason = sel.get("reason", "")

                    # Show knowledge gap card
                    current_mastery = learner.concept_mastery(concept)
                    print_knowledge_gap_card(
                        student_id, concept, current_mastery * 100,
                        learner, style, reason, attempt,
                    )

                    # Check if this is a retry after failure (show adaptation card)
                    if attempt > 1 and prev_sel:
                        prev_style = prev_sel.get("selected_style", "")
                        print_adaptation_card(attempt - 1, prev_style, style, reason)

                    print(f"\n{'─'*50}")
                    print(f"Explanation for: {concept.replace('_', ' ').title()}")
                    print(f"Style: {style.title()} (Attempt {attempt})")
                    print(f"{'─'*50}")
                    print(expl["text"])
                    print(f"{'─'*50}\n")

                    retest_q = get_retest_question(concept, attempt)
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

                    submit_retest(store, run_id, sel["student_id"], concept, ans, s)
                    store.set_state(run_id, RunState.PROBING)

                    # Compute new mastery for the card
                    new_m = learner.concept_mastery(concept)
                    print_retest_result_card(concept, attempt, passed, old_m, new_m)

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
    """Run deterministic demo with 3 personas showing adaptive behavior."""
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
        run_session(sys.argv[2])
    elif cmd == "demo":
        run_demo()
    elif cmd == "replay" and len(sys.argv) >= 3:
        replay_run(sys.argv[2])
    elif cmd == "list":
        list_runs()
    elif cmd == "doctor":
        os.execvp(sys.executable, [sys.executable, "scripts/doctor.py"])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
