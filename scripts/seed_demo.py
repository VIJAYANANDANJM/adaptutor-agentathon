#!/usr/bin/env python3
"""
Seed demo persona histories into the database.

Pre-seeds intervention history and mastery data for 3 demo students,
so the adaptive selector produces different style choices for each
on the SAME knowledge gap (call_stack).

Usage:
    python scripts/seed_demo.py          Seed and show summary
    python scripts/seed_demo.py --clean  Delete demo data first

Can also be imported: `from scripts.seed_demo import seed_histories`
"""
from __future__ import annotations

import os
import sys

# Configure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slice.store import Store


DB_PATH = os.environ.get("SLICE_DB", "run.db")


def seed_histories(store: Store) -> None:
    """Pre-seed intervention history for the 3 demo personas.

    ananya_analogy: 2 past successes with analogy → selector picks analogy
    bharat_trace:   1 past failure with analogy, 2 successes with trace → selector picks trace
    karthik_stuck:  no history (clean slate) → selector picks default, will fail both
    """
    # ── ananya_analogy: strong with analogy ──
    # Give her 2 past analogy successes on different concepts
    store.record_intervention("ananya_analogy", "base_case", "analogy", 1, True)
    store.record_intervention("ananya_analogy", "recursive_step", "analogy", 1, True)
    # Set mastery for previously-seen concepts
    store.upsert_mastery("ananya_analogy", "base_case", 0.85)
    store.upsert_mastery("ananya_analogy", "recursive_step", 0.85)

    # ── bharat_trace: analogy fails, trace works ──
    # Give him 1 analogy failure and 2 trace successes
    store.record_intervention("bharat_trace", "base_case", "analogy", 1, False)
    store.record_intervention("bharat_trace", "base_case", "trace", 2, True)
    store.record_intervention("bharat_trace", "recursive_step", "trace", 1, True)
    # Set mastery
    store.upsert_mastery("bharat_trace", "base_case", 0.70)
    store.upsert_mastery("bharat_trace", "recursive_step", 0.85)

    # ── karthik_stuck: no prior history ──
    # Clean slate — selector will use defaults. He will fail both attempts.
    # (No seeding needed — the lack of data IS the setup)

    print("  ✅ Demo histories seeded:")
    print("     ananya_analogy — 2 analogy wins (100% analogy rate)")
    print("     bharat_trace   — 1 analogy loss, 2 trace wins (100% trace rate)")
    print("     karthik_stuck  — no prior history (default selection)")


def clean_demo_data(store: Store) -> None:
    """Remove demo persona data from the database."""
    demo_ids = ["ananya_analogy", "bharat_trace", "karthik_stuck"]
    for sid in demo_ids:
        store.db.execute("DELETE FROM learner_profiles WHERE student_id=?", (sid,))
        store.db.execute("DELETE FROM intervention_history WHERE student_id=?", (sid,))
    # Also clean up any runs for demo personas
    for run in store.list_runs():
        meta = store.meta(run["id"])
        if meta.get("student_id") in demo_ids:
            store.db.execute("DELETE FROM counters WHERE run_id=?", (run["id"],))
            store.db.execute("DELETE FROM questions WHERE run_id=?", (run["id"],))
            # Can't delete versions (append-only triggers), but we can delete the run
            # Actually we can't delete versions, so just delete the run record
            # The versions will be orphaned but harmless
            store.db.execute("DELETE FROM runs WHERE id=?", (run["id"],))
    print("  🧹 Demo data cleaned.")


def main():
    clean = "--clean" in sys.argv
    store = Store(DB_PATH)

    if clean:
        clean_demo_data(store)

    seed_histories(store)

    # Show summary
    print("\n  Current demo profiles:")
    for sid in ["ananya_analogy", "bharat_trace", "karthik_stuck"]:
        profile = store.get_learner_profile(sid)
        eff = profile["style_efficacy"]
        mastery = profile["mastery"]
        print(f"\n  {sid}:")
        if mastery:
            for c, m in mastery.items():
                print(f"    {c}: {int(m*100)}%")
        else:
            print("    (no mastery data)")
        if eff:
            for style, data in eff.items():
                pct = int(data["rate"] * 100)
                print(f"    {style}: {data['wins']}/{data['total']} ({pct}%)")
        else:
            print("    (no intervention history)")

    store.close()
    print("\n  Done! Run `python run.py demo` to see the adaptive tutor in action.")


if __name__ == "__main__":
    main()
