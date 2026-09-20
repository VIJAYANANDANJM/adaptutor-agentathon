# Walkthrough 3

*Tester:* Sripramod Y  
*Date:* 20 September 2026  
*Duration:* 25 minutes  

## What did you feel was good about the agent?

> "I liked that the agent showed my current learning status and explained what approach it was going to use next. Seeing the previous approach, current mastery and next goal made it easier to understand what the system was doing instead of just getting another question."

## What do you think could be improved?

> "I think it can make the next step more clear and simple. After every attempt, I should be able to quickly see what I have improved, what is still weak and what I have to do next. A small progress summary for the whole topic would also make the experience better."

## Iteration

Based on Sripramod's feedback, we unified the student's learning state, past intervention results, adaptation rationale, and immediate next goals into clean, structured terminal cards.

### Problem Addressed
Previously, student mastery, previous interventions, selected styles, and adaptation reasons were spread across disparate log messages. When a student finished an attempt or improved a concept, it was difficult to quickly discern:
1. **Where am I currently in this concept?**
2. **What did the previous approach achieve?**
3. **Why is the system changing the approach?**
4. **What exactly am I supposed to understand next?**
5. **What happens after I succeed?**

### Experience Implemented
We introduced two complementary, compact UI components:
1. **`🎯 YOUR LEARNING STATE` Card**: Displayed immediately before each explanation and retest.
   - On the first attempt, it shows current mastery, active teaching style, and a concrete learning goal without confusing "previous approach" placeholders.
   - On retries, it highlights `Previous approach: [Style] ❌`, `Result: Did not resolve the gap`, `Next approach: [Style]`, selector reason, and the targeted learning goal.
2. **`✓ CONCEPT IMPROVED` Card**: Displayed immediately when a retest is passed.
   - Shows the student's before-and-after mastery percentage (`42% ➔ 62%`), the positive delta (`+20%`), confirmation that the goal was achieved, and a clean pointer to the next knowledge gap or session completion.
3. **Pedagogical Goal Service**: Concrete, concept-specific targets across all curriculum modules (Recursion, DB Normalization, OS Virtual Memory, IoT MQTT) with dynamic synthesis fallback.

### Changes made

| Dimension | Before | Now on main |
|---|---|---|
| *State Presentation* | Disjointed messages spread across CLI output | Unified `🎯 YOUR LEARNING STATE` card before each intervention |
| *First Attempt State* | N/A or showed generic gap card | Clean view showing current approach & goal without fake prior history |
| *Retry Context* | Only showed style name change | Explicitly displays `Previous approach: [Style] ❌`, failure result, and next style |
| *Learning Goals* | Generic "learn the concept" | Concept-specific targets (e.g., stack frames, 2NF partial dependencies, MQTT QoS) |
| *Success Transition* | Generic retest score text | Dedicated `✓ CONCEPT IMPROVED` card with `old% ➔ new%`, delta, and next step |
| *Next Step Clarity* | Learner had to guess what came next | Explicit `Next ➔ Continue to [Concept]` or `All concepts resolved!` |

## Result

When interacting with AdaptTutor, learners now maintain continuous awareness of their learning trajectory. Retrying a concept clearly contextualizes why the approach changed and what specific principle to master next, while passing a retest immediately celebrates the mastery gain and indicates the exact next step.

### Implementation Commit & Files Changed

* **Commit ID:** `18cada7` — *feat: add clear learning state and next goal presentation*
* **Specific Files Changed:**
  - [`remediation/goals.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/goals.py): Centralized learning goal service (`get_learning_goal`, `get_goal_achieved`) covering Python recursion, relational normalization, OS virtual memory, IoT MQTT, and dynamic synthesis fallback.
  - [`run.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/run.py): Implemented `print_learning_state_card()` and `print_concept_improved_card()`; updated `_drive_session_loop` to advance state machine and render verified mastery deltas and next-step transitions.
  - [`tests/test_goals.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_goals.py): Added 8-test unit and end-to-end integration suite validating concept goals, card presentation formatting, retry context, and session loop execution.

*Verified by:* 8 new unit & integration tests in `tests/test_goals.py` (116/116 tests passing across the repository).
