# AgentSpec — Remediation Loop

**Team:** uniCode
**Members:** Abhijith M, Vijay Anandan J M
**Institution:** B.E. CSE, College of Engineering Guindy, Anna University
**Submitted:** 15 September 2026

---

## 1. The setting

In the third semester at CEG, every B.E. CSE student takes CS3301 Data Structures.
The lab runs in batches of 40–45 students, supervised by one instructor and one
teaching assistant. In Week 6 the topic shifts from iterative constructs to
recursion — and this is where the cohort splits. The students who understood
loops and arrays well enough to pass the first five labs now face a concept that
requires them to hold an unfinished computation in their head while they trace
the next call. Most of them have never done that before.

**Who exactly:** a second-year B.E. CSE student at CEG, sitting a Week 6 lab
session on recursion in Python, having passed the first five weeks on loops and
arrays.

**What they do today:** after a short walkthrough by the instructor, the student
attempts a set of lab questions. When they get one wrong, they re-read their
notes or ask the single instructor — who is already fielding questions from
fifteen other stuck students at the same time. If nobody reaches them, they
copy a working answer from a neighbour and move on without understanding what
went wrong.

**Why that is hard:** the instructor cannot diagnose forty different
misconceptions in a ninety-minute window. Two students can get the same question
wrong for opposite reasons — one does not understand base cases, the other
understands base cases but traces the call stack incorrectly. The fix for each
is different, and there is no time to deliver both. By the time written feedback
arrives (if it arrives at all), the lab has moved on to trees.

## 2. The problem this solves

In the September 2025 DS lab, Batch B had 43 students. The Week 6 recursion
quiz had ten questions. Nineteen students scored below 5 out of 10. The
instructor, Mr. Senthil, spent two and a half hours that weekend writing
individual feedback for those nineteen, then emailed it. Eleven of them opened
the email. Of those eleven, seven replied "thank you sir" and moved on. Four
replied with follow-up questions. By the time Mr. Senthil answered them, the lab
was on Week 8.

The feedback itself was the problem. He wrote the same explanation of base cases
to nine students. For the four who actually engaged, three of them did not need
that explanation — they understood base cases fine but were confused about how
the return value travels back up the stack. Those three received correct
feedback for someone else's problem, and the lab moved on.

The cost was not the instructor's weekend. The cost was that nineteen students
believed they had a recursion problem, were given a single generic explanation,
and three of them had a *different* recursion problem that was never addressed.

## 3. What you are building

**Input:** a student's answers to a fixed set of 8 quiz questions on recursion in
Python, each tagged with the concept it tests (base case recognition, recursive
step tracing, call stack depth, return value propagation).

**Output:** either a confirmation that the student understood the concept (passed
re-quiz after remediation), or a record showing: which concept was
misunderstood, which explanation style was tried, whether it worked, and — if
both styles failed — a flag to the instructor naming the specific student and
the specific concept.

**Never, however much a user wants it:** it does not teach new topics. It does
not generate quiz questions — the questions are fixed and curated by the
instructor beforehand. It does not grade the student or produce a score visible
to the class. It does not replace the instructor's judgement about whether a
student should pass the lab.

**Why this is agentic, in our own words:** the system remembers each student's
answer history and remediation outcomes across runs, in a persistent store —
not in a conversation. It decides *which* explanation style to use based on what
has historically worked for this concept, not a fixed rule. The verify step
re-quizzes the student and can send the run back to select a different
explanation style — the backward arrow. And when both explanation attempts fail,
the system enters a waiting state and suspends until the instructor responds.
The number of times it loops and which path it takes depends on what the student
answers, not on what we hardcoded.

## 4. A complete walkthrough

One student, Priya, from Batch B, taking the Week 6 recursion quiz.

**The quiz** (8 questions, 4 concepts, 2 questions per concept)

| # | concept | question (abbreviated) |
|---|---------|------------------------|
| Q1 | base case | What is the base case in `factorial(n)`? (a) `n == 0` (b) `n == 1` (c) `n < 0` (d) none |
| Q2 | base case | What happens if `countdown(n)` has no base case? (a) returns 0 (b) infinite recursion (c) returns n (d) syntax error |
| Q3 | recursive step | Given `def f(n): return n + f(n-1)` with `f(0)=0`, what is `f(3)`? (a) 3 (b) 6 (c) 9 (d) 0 |
| Q4 | recursive step | In `sum_list([3,1,4])`, how many times is `sum_list` called in total? (a) 3 (b) 4 (c) 2 (d) 1 |
| Q5 | call stack | At the deepest point of `factorial(4)`, how many frames are on the stack? (a) 4 (b) 5 (c) 3 (d) 1 |
| Q6 | call stack | What is the first frame removed from the stack during `factorial(3)`? (a) `factorial(3)` (b) `factorial(1)` (c) `factorial(0)` (d) `factorial(2)` |
| Q7 | return propagation | In `factorial(3)`, what does `factorial(1)` return to `factorial(2)`? (a) 1 (b) 2 (c) 3 (d) 6 |
| Q8 | return propagation | In `fib(4)` (naive), what value does `fib(2)` return? (a) 1 (b) 2 (c) 0 (d) 3 |

---

### Walkthrough A — Priya (one gap, resolved in one attempt)

**Step 1 — quiz.** Priya submits her answers.

```json
{ "kind": "quiz_response", "student_id": "priya_22cs031", "attempt": 1,
  "answers": {
    "Q1": "a", "Q2": "b", "Q3": "b", "Q4": "b",
    "Q5": "a", "Q6": "c", "Q7": "a", "Q8": "a"
  }
}
```

**Step 2 — diagnose.** The system scores against the key. Q5 is wrong — she
answered (a) 4, correct is (b) 5. All others correct. One failed concept:
`call_stack`.

```json
{ "kind": "diagnosis", "student_id": "priya_22cs031",
  "wrong_questions": ["Q5"],
  "concepts_failed": ["call_stack"],
  "concepts_passed": ["base_case", "recursive_step", "return_propagation"]
}
```

**Step 3 — select.** The system checks its store: 6 prior students had a
`call_stack` gap. Style A (analogy) succeeded 4 times. Style B (trace) succeeded
2 times. It picks Style A.

```json
{ "kind": "style_selection", "student_id": "priya_22cs031",
  "concept": "call_stack", "selected_style": "analogy",
  "reason": "analogy succeeded 4/6 times for call_stack; trace succeeded 2/6",
  "attempt": 1
}
```

**Step 4 — explain.** The LLM generates an explanation using the analogy style,
anchored to Priya's specific wrong answer on Q5:

```
You answered that factorial(4) has 4 frames on the stack at its deepest.
Close, but one frame is missing.

Think of the call stack like a stack of cafeteria trays. Each time factorial
calls itself, a new tray goes on top:

  factorial(4) calls factorial(3)  → tray 1
  factorial(3) calls factorial(2)  → tray 2
  factorial(2) calls factorial(1)  → tray 3
  factorial(1) calls factorial(0)  → tray 4
  factorial(0) is the base case — it does not call anyone else, but it is
  still sitting there as tray 5, doing its work (returning 1) before it
  gets removed.

The base case itself occupies a frame. Deepest point = 5 trays, not 4.
```

**Step 5 — retest.** A new question on the same concept, different from Q5:

> At the deepest point of `power(2, 3)` where `power(x, n)` calls
> `power(x, n-1)` with base case `n == 0`, how many frames are on the stack?
> (a) 3  (b) 4  (c) 5  (d) 2

Priya answers (b) 4. Correct — `power(2,3)`, `power(2,2)`, `power(2,1)`,
`power(2,0)` = 4 frames.

```json
{ "kind": "retest_result", "student_id": "priya_22cs031",
  "concept": "call_stack", "style_used": "analogy", "attempt": 1,
  "passed": true
}
```

**Step 6 — evaluate.** Passed. Record the outcome. Run → RESOLVED → COMPLETE.

```json
{ "kind": "outcome", "student_id": "priya_22cs031",
  "concept": "call_stack", "style": "analogy", "passed": true,
  "total_attempts": 1
}
```

---

### Walkthrough B — Ravi (one gap, resolved on second attempt — the backward arrow)

Ravi also gets Q5 wrong (`call_stack`), plus Q7 wrong (`return_propagation`).
Two gaps diagnosed.

**First gap: call_stack.** System picks Style A (analogy). Ravi gets the
explanation, takes the re-quiz, and **fails** — he answers (a) 3.

**The backward arrow fires.** EVALUATE sees: Style A tried, failed. Style B not
tried. Run returns to SELECT.

```json
{ "kind": "style_selection", "student_id": "ravi_22cs044",
  "concept": "call_stack", "selected_style": "trace",
  "reason": "analogy tried and failed for this student; switching to trace",
  "attempt": 2
}
```

The trace explanation is generated — a step-by-step execution table:

```
| call            | n | action                  | frames on stack |
|-----------------|---|-------------------------|-----------------|
| power(2, 3)     | 3 | calls power(2, 2)       | 1               |
| power(2, 2)     | 2 | calls power(2, 1)       | 2               |
| power(2, 1)     | 1 | calls power(2, 0)       | 3               |
| power(2, 0)     | 0 | base case, returns 1    | 4 ← deepest     |
```

**Step 5 (attempt 2) — retest.** Ravi gets a different variant question:

> In `sum_to(5)` where `sum_to(n)` calls `sum_to(n-1)` with base case `n == 0`,
> how many frames are on the stack at the deepest point?
> (a) 5  (b) 6  (c) 4  (d) 7

Ravi answers (b) 6. Correct — `sum_to(5)` through `sum_to(0)` = 6 frames.

```json
{ "kind": "retest_result", "student_id": "ravi_22cs044",
  "concept": "call_stack", "style_used": "trace", "attempt": 2,
  "passed": true
}
```

**Step 6 (attempt 2) — evaluate.** Passed on the second attempt. The system
records that the trace style succeeded where the analogy style did not.

```json
{ "kind": "outcome", "student_id": "ravi_22cs044",
  "concept": "call_stack", "style": "trace", "passed": true,
  "total_attempts": 2
}
```

`call_stack` resolved via Style B. The system then processes Ravi's second gap
(`return_propagation`) using the same loop.

---

### Walkthrough C — Karthik (both styles fail — the human pause)

Karthik fails the re-quiz after Style A and again after Style B. Revision limit
reached (2 attempts on `call_stack`).

```json
{ "kind": "instructor_flag", "student_id": "karthik_22cs012",
  "concept": "call_stack",
  "styles_tried": ["analogy", "trace"],
  "both_failed": true,
  "state": "waiting_instructor",
  "message": "Karthik (22CS012) could not demonstrate understanding of call
              stack depth after two explanation attempts. Needs instructor."
}
```

Run enters **WAITING_INSTRUCTOR**. Nothing happens until the instructor responds.
If the instructor does not respond by session end, the output reads:
*"Flagged for instructor — no response received. Concept: call stack.
Status: unresolved."*

The student sees: *"Your instructor has been notified about your difficulty
with call stack depth. You will hear back soon."* — not a fabricated explanation,
not silence.

## 5. Who is doing the thinking

| step | the agent does it | the human does it | what the human loses if the agent does it |
|---|---|---|---|
| Scoring quiz answers against the fixed key | yes | | nothing — the key is set beforehand |
| Diagnosing which concept the wrong answer maps to | yes | | nothing — each question is pre-tagged |
| Choosing which explanation style to try first | yes, from stored success rates | | nothing — the rule is mechanical: pick the higher win rate |
| Generating the explanation text | yes (LLM call) | | nothing, as long as it stays within the concept and style constraints |
| Deciding whether the re-quiz answer is correct | yes | | nothing — fixed-answer multiple choice |
| Deciding a student needs instructor help | yes (both styles failed = flag) | | nothing — the rule is: two failures = flag |
| Deciding **what** to do about the flagged student | | the instructor | everything — the agent has exhausted its options; the instructor's judgement is the whole point |
| Answering the quiz and the re-quiz | | the student | everything — if the agent answers for the student, no learning happens |
| Curating the quiz questions and answer key | | the instructor (before the session) | the quality of the diagnosis — bad questions produce bad signal |

**If your agent asks a person something:**

**The question it asks, and who answers it:** after both styles fail for a
student on a specific concept, the system posts a structured message: student
name, register number, concept name, which two styles were tried, and what the
student answered both times. The instructor reads it and either types a custom
hint or notes "schedule 1-on-1."

**What happens if nobody answers, and how the output shows that:** the run stays
in WAITING_INSTRUCTOR. The student's record shows *"flagged for instructor — no
response received"* and the concept stays `unresolved`. It does **not** generate
a third explanation attempt or pretend the student understood. The flag persists
in the store and is visible on the next session — it does not vanish.

## 6. The state machine

```
  QUIZ ──▶ DIAGNOSE ──▶ SELECT ──▶ EXPLAIN ──▶ RETEST ──▶ EVALUATE
                          ▲                                   │
                          └────── (failed, other style ───────┘
                                   available)
                                                              │
                                            (both failed) ────┘
                                                              ▼
                                                  WAITING_INSTRUCTOR
                                                       │          │
                                          (responded) ─┘          └─ (timeout)
                                              ▼                        ▼
                                           RESOLVED          CLOSED_UNRESOLVED

  EVALUATE ──passed──▶ RESOLVED ──more concepts?──▶ SELECT (next concept)
                                  ──no more──▶ COMPLETE
```

| state | active / waiting / finished | what moves it on |
|---|---|---|
| QUIZ | active | student submits answers |
| DIAGNOSE | active | scoring produces a list of failed concepts |
| SELECT | active | system picks Style A or B from stored success rates |
| EXPLAIN | active | LLM generates explanation in selected style |
| RETEST | active | student answers a new question on the same concept |
| EVALUATE | active | re-quiz scored; pass → RESOLVED, fail + untried style → SELECT, fail + both tried → WAITING_INSTRUCTOR |
| WAITING_INSTRUCTOR | **waiting** | instructor replies or session times out |
| RESOLVED | active | concept marked learned; more concepts → SELECT for next; else → COMPLETE |
| COMPLETE | **finished** | nothing |
| CLOSED_UNRESOLVED | **finished** | nothing — the flag stays in the record |

**What can send work backwards:** the EVALUATE step. When the re-quiz fails and
one explanation style has not been tried, the run goes back to SELECT to pick the
other style. This is the backward arrow — the number of times it fires depends
on what the student answers, not on what we coded.

**What the run decides that the diagram cannot show:** which path through EVALUATE
a given student takes. Priya went straight through. Ravi looped once. Karthik hit
the wall. The route is different for each, decided at runtime.

**Spend limit — what bounds cost:** 10 model calls per student per session. Each
explanation generation is one call. If a call fails and retries, the retry
counts here.

**Revision limit — what bounds going backwards:** 2 explanation attempts per
concept per student. Counted from the number of `style_selection` records for
this student–concept pair, not from the spend counter. After 2 attempts, flag
the instructor. The counters are separate: a retried LLM call burns spend
budget but does not consume a revision.

## 9. The second encounter

**Case 1 — Karthik returns after the instructor responded.** The run was in
WAITING_INSTRUCTOR. The instructor typed: *"Karthik, draw the stack yourself on
paper for factorial(3), writing each frame as a box. Count the boxes."*
Karthik's run resumes at RETEST with a new verification question. If he passes,
`call_stack` moves to RESOLVED and the record reads: *"resolved after instructor
intervention."* If he fails again, the instructor is notified a second time with
the new failure — the system does not loop further on its own.

**Case 2 — Priya takes next week's quiz (trees with recursion).** Her Week 6
record is in the store. The system knows analogies worked for her on
`call_stack`. If a tree-traversal question tests a recursion concept and she gets
it wrong, the system's SELECT step reads her history and picks the analogy style
first — because that is what worked for her before. It does not start from
scratch.

**Case 3 — a new student, Deepa, encounters `call_stack` for the first time.**
The system has no history for Deepa, but it has population-level data: across
all students, analogy succeeded 5 times for `call_stack`, trace succeeded 3
times. Deepa gets analogy first. Her outcome is recorded and updates the
population stats.

**What a fresh conversation could not do:** it would not know that Priya
responds to analogies, that Ravi needed a trace table, or that Karthik was stuck
after two attempts. Those per-student style histories and the population success
rates are the stored state that makes the second encounter different from the
first.

## 11. What this deliberately does not do

1. **It does not generate quiz questions.** The quiz content is curated and fixed
   by the instructor before the session. Generating questions introduces a new
   failure mode (badly constructed questions) that we cannot verify in two days,
   and it is not the problem we are solving. The problem is remediation after a
   wrong answer, not assessment design.

2. **It does not cover more than one topic.** Scope is recursion in Python — one
   chapter, one week. Expanding to arrays, sorting, trees would mean tagging
   hundreds of questions, writing explanation templates for each concept × each
   style, and testing all of them. We chose depth on one topic over breadth
   across many — a working loop on recursion is more valuable than a broken loop
   across five topics.

3. **It does not grade or rank students.** The system helps a stuck student get
   unstuck. It does not produce a mark, does not tell the instructor who is
   "smart" or "weak," and does not create a leaderboard. Deliberate: the moment
   a student fears that asking for help will hurt their grade, they stop asking.

4. **It does not support competing remediation agents.** Our Round 1 deck
   proposed three specialist agents with trust scores. We are cutting that to
   two fixed explanation styles (analogy, trace) with a simple win-rate selector.
   The multi-agent trust scoring and reputation learning are future scope. They
   add architectural complexity without adding evidence we can gather in 48
   hours.

5. **It does not build an instructor dashboard.** If time permits, we show flags
   in a terminal or a single-page web view. But the dashboard is not the agent —
   it is a read-only view on top of the agent's stored records. We build the
   records first and the view last, if at all.

## 12. Build order

| phase | what lands | hours |
|---|---|---|
| 1 | State machine wired end-to-end with **hard-coded fake data**. Quiz → Diagnose → Select (always picks A) → Explain (returns a canned string) → Retest (student input simulated) → Evaluate → Resolved → Complete. The backward arrow works: if retest returns "fail," the run returns to Select and picks B. Instructor flag fires after 2 failures. All with no LLM call. | 5 |
| | *cut line: the loop going backwards, the revision limit, and the instructor flag — demonstrated entirely on fake data. This already shows every agentic property.* | |
| 2 | Real LLM calls for explanation generation. The explain step sends concept, wrong answer, and style to the model and gets a tailored explanation. Student answers the re-quiz through a terminal prompt or simple web form. Records stored to JSON via `slice/store.py`. Run survives being killed and restarted. | 5 |
| | *cut line: a real student answer produces a real, style-specific explanation, and every step is stored durably.* | |
| 3 | The waiting state works for real: instructor flag triggers WAITING_INSTRUCTOR, the process can exit, instructor responds later, run resumes. Historical style selection: the SELECT step reads all past outcomes for this concept and picks the style with the higher success rate — not just "A then B." | 4 |
| | *cut line: the second encounter works — a returning student benefits from the system's memory.* | |
| 4 | **Walkthroughs and evidence.** Three classmates take the quiz and go through the remediation loop. One person deliberately tries to break it (answers all wrong, types nonsense, closes the window mid-session). We fix at least one thing we observe. Clean up output for the demo. Write up what we changed and why. | 5 |

**Where the hours will actually go:** Phase 2 — specifically, getting the LLM to
produce explanations that are genuinely different between the two styles and that
address the *specific* wrong answer rather than reciting a generic recursion
lecture. We will spend most of that time re-reading outputs and rewriting the
style prompt, not writing Python.

**Second bottleneck:** Phase 4. Finding three classmates willing to sit through
a recursion quiz during a hackathon. We need names and times booked before the
event — Saturday morning, 20 minutes each.

## 15. What you are least sure about

1. **The right prompt structure to make the two explanation styles feel
   genuinely distinct.** Analogy-based and trace-based explanations target
   different learning preferences — analogies build intuition, traces build
   precision. The open question is prompt engineering: how to constrain the LLM
   so Style A always uses a concrete real-world comparison and Style B always
   produces a step-by-step execution table, without the two drifting toward
   similar prose. **Validation plan:** on Saturday morning, generate both styles
   for Q5, show them side-by-side to a classmate, and confirm they feel like two
   different approaches. If they converge, we tighten the style constraints in
   the prompt before building further.

2. **The difficulty calibration of re-quiz variants.** Each re-quiz question
   needs to test the same concept as the original but with different surface
   details — close enough that the explanation is relevant, different enough that
   the student cannot answer from pattern-matching alone. We have designed 8
   variants and the balance between "too similar" and "too different" is
   something we will tune with live testers. **Validation plan:** after showing
   a tester the explanation for Q5, give them the re-quiz variant and ask them
   to explain their reasoning. This tells us whether the variant is testing
   understanding or recall.

3. **Signal strength from two questions per concept.** With only two questions
   per concept, a single wrong answer could be a misread rather than a genuine
   gap. We chose this trade-off deliberately — a longer quiz reduces engagement,
   and our remediation loop catches false positives naturally (if the student
   passes the re-quiz easily, the "gap" was likely noise). **Mitigation in the
   output:** the system reports confidence level — *"1 of 2 wrong (moderate
   signal)"* vs *"2 of 2 wrong (strong signal)"* — so the remediation is
   transparent about the evidence it is acting on.
