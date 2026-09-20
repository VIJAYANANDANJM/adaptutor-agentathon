# Walkthrough 2

*Tester:* Jeeva S  
*Date:* 20 September 2026  
*Duration:* 25 minutes  

## What did you feel was good about the agent?

> "I liked that when I got the retest wrong, it was not just showing that the answer is wrong. It was able to explain the reason behind my selected option and connect it to the actual concept. For example, if I misunderstood how a recursive call returns, it explains that the caller continues only after the recursive call is completed. So I can understand where exactly I went wrong."

## What do you think could be improved?

> "After I get the retest wrong, it can first explain exactly what was wrong with my new answer before changing to another teaching method. Instead of directly moving to the next intervention, it can say something like, 'You selected B because you thought X, but actually Y.' That will make it much more clear what mistake I made in the retest."

## Iteration

Based on Jeeva's feedback, we updated the failed-retest workflow so that the system immediately pauses to diagnose the learner's actual mistake before transitioning to the next intervention style.

### Problem Addressed
Previously, when a student answered a retest question incorrectly, the remediation loop immediately triggered the backward loop:
$$\text{Retest Wrong} \longrightarrow \text{Switch Teaching Style} \longrightarrow \text{New Explanation}$$
The learner was notified that their retest failed, but they received zero feedback explaining **why** their newly selected option was flawed before being pushed into a new teaching style.

### Flow Implemented
We enhanced the failed-retest lifecycle to:
$$\text{Retest Failed} \longrightarrow \text{Targeted Mistake Diagnosis} \longrightarrow \text{Adaptive Style Selection} \longrightarrow \text{New Intervention} \longrightarrow \text{Next Retest}$$

### Changes made

| Dimension | Before | Now on main |
|---|---|---|
| *Retest Failure Response* | Only scored pass/fail; immediately pivoted to next style | Emits targeted `RetestFeedback` card explaining the exact mistake |
| *Option Context* | Discarded selected option text after boolean evaluation | Extracts learner's selected option text vs. correct option text |
| *Misconception Explanation* | None; learner was left wondering why their choice failed | LLM synthesizes `why_wrong` (<50 words) and `what_to_remember` (<25 words) |
| *Resilience & Fallback* | N/A | Deterministic concept-aware fallback if LLM times out or is offline |
| *CLI Presentation* | Only showed `FAILED ❌` | Renders a dedicated `🔍 RETEST FEEDBACK — MISTAKE DIAGNOSIS` card |
| *Observability & State* | No feedback record in state machine | Persisted as immutable `retest_feedback` version in SQLite `run.db` |

## Result

When a student now fails a retest, AdaptTutor explicitly identifies the misconception behind the chosen option (e.g., *"You selected [A] 'It is popped and replaced'. This assumes activation records return or clear immediately, but in recursion each function invocation maintains its own distinct frame..."*), provides a key takeaway to remember, and only then presents the adaptation card and alternative pedagogical style.

### Implementation Commit & Files Changed

* **Commit ID:** `6a9308c` — *feat: add mistake-specific feedback after failed retests based on walkthrough 2*
* **Specific Files Changed:**
  - [`remediation/schema.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/schema.py): Added `RetestFeedback` domain model storing `student_id`, `concept`, `attempt`, `selected_option`, `selected_text`, `correct_option`, `correct_text`, `why_wrong`, `what_to_remember`, and source.
  - [`remediation/feedback.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/feedback.py): Created the diagnosis component generating targeted mistake feedback via OpenRouter LLM (`MistakeAnalysisSchema`) with concept-aware deterministic fallbacks.
  - [`remediation/flow.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/flow.py): Hooked feedback generation into `_evaluate()` on failed retests and appended `retest_feedback` records to SQLite.
  - [`run.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/run.py): Added `print_retest_feedback_card()` and updated `_drive_session_loop` to render the diagnosis card immediately following a failed retest.
  - [`tests/test_feedback.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_feedback.py): Added 6-test suite verifying feedback generation, option text accuracy, adaptation continuation, and fallback resilience.

*Verified by:* 6 new unit & integration tests in `tests/test_feedback.py` (108/108 tests passing across the repository).

