# Stress Testing

*Tester:* Vikram Dharshan  
*Date:* 20 September 2026  
*Duration:* 35 minutes  

## What did you feel was good about the agent?

> "I stress-tested the tutor with extreme learner behavior—repeatedly failing diagnostic questions, entering invalid choices, purposely giving incorrect answers across consecutive retests, and interrupting the process mid-flow. The deterministic core and SQLite persistence held up remarkably well. There were no database lockups, no crashes from unhandled state exceptions, and the system never hallucinated test scores or allowed corrupted state transitions."

## What do you think could be improved?

> "When I intentionally pushed a concept to failure across multiple rounds, I noticed a critical stress boundary: the curated retest question pool eventually ran out. Under repeated failures, the system shouldn't repeat the exact same retest questions, get stuck in an unhandled loop, or abruptly escalate to an instructor without giving the student a different mode of support. 
> 
> When the questions run out, it should recognize that more standard testing isn't working and switch into an interactive Guided Practice mode with small, bite-sized reasoning steps. Furthermore, each guided step must have a strict retry limit (at most 1 retry) so the learner cannot get trapped in an infinite loop inside practice mode. Once they complete the guided steps, they should get a fresh, unseen retest question."

## Iteration

Based on Vikram Dharshan's stress testing feedback, we implemented **Retest Pool Exhaustion Detection, Guided Practice Engine, and Fresh Retest Delivery**.

### Problem Addressed
During adversarial and repeated-failure stress testing:
1. **Finite Question Pool Exhaustion**: Standard curriculum modules contain a finite number of retest questions (typically 2–3 per concept). If a learner repeatedly failed, the system lacked a principled mechanism to avoid repeating questions while ensuring the remediation flow continued constructively.
2. **Pedagogical Deadlock**: Prematurely escalating a student to an instructor after exhausting retest questions misses an opportunity for scaffolded, active-recall intervention.
3. **Infinite Loop Risk in Practice**: Any multi-step practice introduced to resolve exhaustion had to be strictly bounded with a maximum of 1 retry per step to prevent infinite looping under continuous failure.
4. **State Persistence Across Restarts**: If a student drops off or the terminal restarts during guided practice, the progress across individual steps must resume cleanly without data loss.

### Flow Implemented
We enhanced the system to transition through Guided Practice when the retest pool is exhausted:

```text
Initial Diagnostic Question
            ↓ (Wrong)
Targeted Intervention
            ↓
        Retest Q1
            ↓ (Wrong)
        Retest Q2
            ↓ (Wrong)
... [All unused retest questions exhausted]
            ↓
 ⚠️ RETEST POOL EXHAUSTED
            ↓
     GUIDED PRACTICE
   (2–4 micro-steps,
  1-retry bound per step)
            ↓
✓ GUIDED PRACTICE COMPLETE
            ↓
   Fresh Independent Retest
```

### Changes made

| Dimension | Before | Now on main |
|---|---|---|
| *Question Pool Tracking* | Only recorded pass/fail; did not track specific question texts | Tracks attempted question texts per concept in SQLite to ensure no question repeats while unused ones remain |
| *Exhaustion Handling* | Could repeat questions, abort, or prematurely escalate to instructor | Detects pool exhaustion explicitly and switches into `GUIDED PRACTICE` mode |
| *Pool Exhaustion Card* | None | Renders dedicated `⚠️ RETEST POOL EXHAUSTED` notification card |
| *Guided Scaffolding* | None | Delivers concept-specific 2–4 step progressive reasoning exercises (curated for recursion & normalization; dynamic synthesis fallback for custom modules) |
| *Step Retry Bounding* | N/A | Strictly limits incorrect answers to **at most 1 retry per step** with targeted hints, preventing infinite loops |
| *Post-Practice Transition* | N/A | Displays `✓ GUIDED PRACTICE COMPLETE` card and delivers an independent `Fresh Retest` |
| *Crash Resumption* | Interrupted sessions could lose mid-remediation sub-state | `get_guided_practice_progress` reads SQLite events to resume directly at the next unfinished practice step |
| *Learner Model Integrity* | N/A | Logs intervention with `style="guided_practice"` while keeping EMA mastery formulas intact |

---

## Result

Under repeated-failure stress testing, AdaptTutor now exhibits complete robustness:
- When questions for a concept run out, the system avoids repeated questions and transitions seamlessly into Guided Practice with clear terminal notifications.
- In Guided Practice, the student works through structured reasoning steps with immediate feedback. If the student answers incorrectly, they receive a targeted hint and exactly one retry before the system explains the step and advances, guaranteeing termination.
- Upon completion, the student receives a fresh, independent retest question from a dedicated bank.
- Interrupting the process mid-step and re-running `python run.py session <student_id>` resumes cleanly from the exact step where the learner left off.

---

### Implementation Commit & Files Changed

* **Commit ID:** [`4654f9d`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor) — *feat: add retest pool exhaustion detection, guided practice, and fresh retest delivery*
* **Specific Files Changed:**
  - [`remediation/schema.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/schema.py): Added `question_text` and `correct_answer` to `RetestResult`; added `GuidedStep` and `GuidedPracticeRecord` models.
  - [`remediation/practice.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/practice.py): Implemented question tracking (`get_attempted_question_texts`, `is_retest_pool_exhausted`), curated guided practice banks for Python recursion and DB normalization, dynamic step synthesis fallback, 1-retry limit enforcement, fresh retest bank, and SQLite event persistence.
  - [`remediation/flow.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/flow.py): Intercepted retest failure in `_evaluate()` to trigger `pool_exhaustion` and `awaiting_guided_practice` instead of premature instructor escalation.
  - [`run.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/run.py): Added `print_pool_exhausted_card()`, `print_guided_practice_complete_card()`, and `run_guided_practice_session()`; integrated step execution, 1-retry bounding, learner model intervention logging, and fresh retest delivery into `_drive_session_loop()`.
  - [`tests/test_practice.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_practice.py): Added 9 dedicated stress and resilience tests validating non-repetition, exhaustion detection, step delivery, 1-retry bounding, SQLite history, fresh retests, crash resumption, and fallback synthesis.
  - [`tests/test_scenarios.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_scenarios.py): Updated end-to-end scenario tests to handle guided practice state transitions.
  - [`tests/test_feedback.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_feedback.py): Integrated feedback tests with the guided practice lifecycle.

*Verified by:* 9 dedicated unit and integration tests in `tests/test_practice.py` (**125 / 125 tests passing** across all 12 test suites in the repository, zero regressions).
