#!/usr/bin/env python3
"""
AdaptTutor CLI entrypoint.

Usage:
    python run.py session <student_id>      Start or resume a remediation session
    python run.py replay <run_id>           Replay a past run's history
    python run.py list                      List recent runs
    python run.py doctor                    Run environment diagnostics

Environment:
    LLM_MODE=mock      Use deterministic canned responses (default, no API key needed)
    LLM_MODE=real      Use OpenRouter LLM (requires OPENROUTER_API_KEY in .env)
"""
from __future__ import annotations

import json
import sys
import os

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

DB_PATH = os.environ.get("SLICE_DB", "run.db")


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
    while True:
        state = advance(store, run_id, flow, s)

        if state == RunState.COMPLETE:
            print("\nAll concepts resolved. Session complete.")
            break
        elif state == RunState.FAILED:
            print("\nSession ended.")
            break
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

                    print(f"\n{'─'*50}")
                    print(f"Explanation for: {concept.replace('_', ' ').title()}")
                    print(f"Style: {sel['selected_style'].title()} (Attempt {attempt})")
                    print(f"{'─'*50}")
                    print(expl["text"])
                    print(f"{'─'*50}\n")

                    retest_q = get_retest_question(concept, attempt)
                    print(f"Retest: {retest_q.text}")
                    for opt, text in retest_q.options.items():
                        print(f"  ({opt}) {text}")

                    while True:
                        ans = input(f"Your answer [{'/'.join(retest_q.options.keys())}]: ").strip().lower()
                        if ans in retest_q.options:
                            break
                        print("  Please enter a valid option.")

                    submit_retest(store, run_id, sel["student_id"], concept, ans, s)
                    store.set_state(run_id, RunState.PROBING)
                    continue
                else:
                    break
            else:
                print("\nYour instructor has been notified. You will hear back soon.")
                break
        else:
            break

    store.close()


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
