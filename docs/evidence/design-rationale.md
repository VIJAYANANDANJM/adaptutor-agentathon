# Design Rationale & Architectural Decisions

**Project:** AdaptTutor (Adaptive Computer Science Remediation System)  
**Team:** Team uniCode — College of Engineering Guindy (CEG), Anna University  
**Event:** Agentathon 2026  
**Document:** Evidence of System Design & Pedagogical Rationale  

---

## 1. Executive Rationale: The Agentic Slice Philosophy

Most conversational AI tutors built atop raw Large Language Models fail in classroom and lab settings due to two fatal architectural flaws:
1. **Hallucinatory Grading & Unbounded State**: When an LLM is asked to both evaluate student answers and orchestrate conversation, it hallucinates quiz scores, deviates from curricula, forgets past context, and enters infinite conversational loops.
2. **Pedagogical Monoculture**: Delivering a single, generic explanation to all struggling students fails because different students have fundamentally different cognitive models (e.g., intuitive/visual learners vs. mechanical/trace-oriented learners).

### The Solution: Strict Separation of Concerns
AdaptTutor adopts the **Agentic Slice architecture**:
- **Deterministic Python Engine**: Governs all quiz scoring, set-difference gap diagnosis, multi-armed bandit style selection, EMA mastery calculations, loop bounds, exhaustion tripwires, and instructor escalations.
- **Isolated LLM Choke Point**: The Large Language Model (`slice/llm.py`) is restricted to a single gateway function (`complete()`) and used **exclusively** for high-value pedagogical text generation: generating personalized explanations, diagnosing retest misconceptions, and synthesizing dynamic curriculum modules.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        DETERMINISTIC PYTHON LAYER                      │
│                                                                        │
│  • Diagnostic Quiz Scoring     ──> Exact string match vs. answer_key   │
│  • Knowledge Gap Diagnosis     ──> Set-difference math                 │
│  • Style Selection Algorithm   ──> 0.7 * StudentRate + 0.3 * CohortRate│
│  • Revision Loop Fencing       ──> MAX_REVISIONS = 2 per concept       │
│  • Retest Pool Exhaustion      ──> Detected in practice.py             │
│  • Step Retry Bounding         ──> Maximum 1 retry per guided step     │
│  • Retest Evaluation           ──> Exact match vs. verified retest key │
│  • Mastery Tracking (EMA)      ──> SQLite learner_profiles             │
│  • Human Escalation Callback   ──> State transition: AWAITING_EXPERT   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                     Only High-Value Text Generation
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         ISOLATED LLM LAYER                             │
│                                                                        │
│  • slice/llm.py Choke Point    ──> Single complete() function          │
│  • Pedagogical Text Synthesis  ──> Generate Analogy or Trace text      │
│  • Mistake Diagnosis           ──> Analyze student's selected choice   │
│  • Curriculum Synthesis        ──> Generate complete 4-concept module  │
│  • Pydantic Schema Validation  ──> Enforced output contracts           │
│  • Single-Pass Self Repair     ──> Fixed schema reflection on failure  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Key Pedagogical & Architectural Decisions

### Decision 1: Dual-Style Pedagogical Modeling (Analogy vs. Trace)
* **Rationale**: Educational research in computer science pedagogy indicates that recursion misconceptions split into two primary categories: operational/mechanical confusion (how the stack unwinds) and conceptual/mental model confusion (what recursion represents).
* **Implementation**:
  - **Analogy**: Anchors abstract execution to tangible real-world systems (e.g., cafeteria tray stacks, Russian nesting dolls, relay race batons) without code blocks or pseudocode (<180 words).
  - **Trace**: Uses mechanical step-by-step frame accumulation, parameter state tracking, and return value substitution.
* **Backward Adaptation**: If a student fails with Analogy on Attempt 1, Attempt 2 is strictly constrained to switch to Trace (and vice-versa). The student never receives the same failed approach twice.

---

### Decision 2: Context Enrichment & 3-Part Scaffolding
* **Empirical Trigger**: Walkthrough 1 with **Roopa Varshni** ([`walkthrough-1.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-1.md)).
* **Problem**: Originally, the LLM received only raw letter choices (`wrong='b'`, `correct='a'`) without option text. The LLM was blind to what distractor the student chose.
* **Design Decision**:
  - Injected full option dictionaries into the prompt.
  - Explicitly tagged distractors: `[STUDENT'S WRONG CHOICE]` vs `[CORRECT ANSWER]`.
  - Injected student mastery %, attempt history, and learning objectives.
  - Implemented a 3-part analogy scaffold: **Physical Anchor $\to$ Misconception Hook $\to$ Resolution**.
* **Impact**: Explanations directly explain why the student's chosen mental model failed rather than providing generic textbook definitions.

---

### Decision 3: Mistake-Specific Feedback After Failed Retests
* **Empirical Trigger**: Walkthrough 2 with **Jeeva S** ([`walkthrough-2.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-2.md)).
* **Problem**: Previously, answering a retest incorrectly immediately triggered style adaptation without explaining *why* the newly chosen option was wrong. Students were confused about their mistake before entering the next intervention.
* **Design Decision**:
  - Intercepted retest failure in `_evaluate()`.
  - Created `remediation/feedback.py` and `RetestFeedback` model.
  - Generates a focused `🔍 RETEST FEEDBACK — MISTAKE DIAGNOSIS` card:
    - `Why your answer was wrong`: Flaw in the student's specific choice (<50 words).
    - `What to remember`: Single memorable takeaway (<25 words).
  - Added concept-aware deterministic fallbacks if the LLM is offline or times out.

---

### Decision 4: Transparent Learning State & Immediate Next Goals
* **Empirical Trigger**: Walkthrough 3 with **Sripramod Y** ([`walkthrough-3.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-3.md)).
* **Problem**: Students reported that mastery percentages, past attempts, and adaptation reasons were scattered across CLI messages, making it difficult to understand where they stood.
* **Design Decision**:
  - Created `remediation/goals.py` providing concrete pedagogical objectives for every concept.
  - Built `🎯 YOUR LEARNING STATE` card displayed before every intervention:
    - Initial Attempt: Shows concept, current mastery progress bar, and immediate learning goal.
    - Retry Attempt: Shows previous approach with failure tag (`Previous approach: Analogy ❌`), failure result, next approach, adaptation reason, and goal.
  - Built `✓ CONCEPT IMPROVED` card displayed upon passing:
    - Shows before-and-after progression (`10% ➔ 55% (+45%)`), goal achieved confirmation, and clear next step pointer.

---

### Decision 5: Retest Exhaustion → Guided Practice → Fresh Retest
* **Empirical Trigger**: Adversarial Stress Testing with **Vikram Dharshan** ([`stress-testing.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/stress-testing.md)).
* **Problem**: Standard curriculum banks contain finite retest questions (typically 2–3 per concept). Under repeated failures, questions could repeat, loops could spin infinitely, or students were prematurely escalated without scaffolded practice.
* **Design Decision**:
  - **Question Tracking**: Logs attempted question texts in SQLite; guarantees questions never repeat while unused questions exist.
  - **Exhaustion Detection**: When curated retests run out, explicitly triggers `⚠️ RETEST POOL EXHAUSTED` and switches to `GUIDED PRACTICE`.
  - **Guided Practice**: Delivers 2–4 concept-specific micro-steps with immediate feedback.
  - **1-Retry Bound per Step**: Limits retries to at most 1 per step with hints, preventing infinite loops.
  - **Fresh Retests**: Upon completing guided practice (`✓ GUIDED PRACTICE COMPLETE`), presents an independent, unseen validation question from a dedicated fresh bank.
  - **Crash Resumption**: Automatically resumes from SQLite event logs across terminal restarts.

---

## 3. Mathematical & Algorithmic Foundations

### Multi-Armed Bandit Style Selector
To select the optimal instructional style for a student on a given concept, AdaptTutor employs a weighted multi-armed bandit algorithm:

$$\text{Score}(\text{style}) = 0.7 \times \text{StudentWinRate}(\text{style}) + 0.3 \times \text{CohortWinRate}(\text{style})$$

- **Individual Affinity ($0.7$ weight)**: Prioritizes the individual learner's historical success with this style.
- **Cohort Wisdom ($0.3$ weight)**: Solves the cold-start problem for new learners by leveraging population-level efficacy across the cohort.
- **Deterministic Tie-Breaking**: Defaults to `"analogy"` when scores tie, ensuring 100% reproducible execution.

### Exponential Moving Average (EMA) Mastery
Mastery is tracked per concept in the SQLite `learner_profiles` table:
- **Diagnostic Error**: Initializes mastery to **25%** ($0.25$), creating an active Knowledge Gap.
- **Diagnostic Correct**: Initializes mastery to **85%** ($0.85$).
- **Retest Passed**: Adds **$+45\%$** ($+0.45$), capped at **95%** ($0.95$).
- **Retest Failed**: Penalizes **$-15\%$** ($-0.15$), floored at **10%** ($0.10$).
- **Classification**: Concepts $\ge 75\%$ are tagged `STRONG`; concepts $< 60\%$ are tagged `WEAK`.

---

## 4. Resilience & Security Engineering

| Design Invariant | Failure Mode Prevented | Architectural Defense |
|---|---|---|
| **Append-Only SQLite Persistence** | State corruption, data loss, untraceable bugs | Database triggers forbid `UPDATE` and `DELETE` on the `versions` table. All state is reconstructed from immutable event logs. |
| **Budget Fences** | Runaway LLM spending, infinite API loops | Hard database-enforced limits: max 10 model calls per session, max 2 revisions per concept. |
| **Bounded Retry Loops** | Infinite retry cycles under continuous failure | At most 1 retry per guided practice step; maximum revisions per concept capped at 2. |
| **Single-Pass Self Repair** | LLM schema deviations or markdown fences | `_strip_fence()` cleans code blocks; `_repair()` feeds validation errors back to the model once. If repair fails, falls back gracefully. |
| **Network Outage Resilience** | Terminal crash or deadlock during internet drops | Real LLM calls catch `httpx.RequestError` with 3-tier backoff; failure records are written to SQLite; deterministic fallbacks preserve student sessions. |
| **Process Suspension (`AWAITING_EXPERT`)** | Lost context during instructor escalation | Sessions write an immutable escalation record and halt cleanly without consuming CPU or memory. Re-invoking `advance()` resumes immediately when instructor guidance arrives. |

---

## 5. Topic-Agnostic Extensibility Rationale

While AdaptTutor was initially built for Week 6 Python Recursion, the domain engine was decoupled to support any computer science topic:
1. **JSON as Single Source of Truth**: Modules in `data/modules/` (`python_recursion.json`, `db_normalization.json`, `operating_systems_virtual.json`, `iot_mqtt.json`) encapsulate concepts, answer keys, diagnostic quizzes, retest banks, and domain-specific style instructions.
2. **AI Curriculum Generator**: Instructors can run `python run.py generate-curriculum "<topic>"` to autonomously synthesize a fully structured 4-concept course module with zero manual code editing.
3. **Dynamic Prompts**: The runtime engine (`remediation/provider.py`) dynamically wraps module instructions into rigorous pedagogical prompts with universal guardrails.

---

*Authored by Team uniCode (College of Engineering Guindy) for Agentathon 2026.*
