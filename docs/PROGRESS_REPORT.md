# AdaptTutor — Comprehensive Project Progress Report

**Project:** AdaptTutor (Adaptive Remediation & Intelligent Tutoring System)  
**Institution:** College of Engineering Guindy — Team uniCode  
**Event:** Agentathon 2026  
**Date:** September 20, 2026  
**Repository:** `https://github.com/VIJAYANANDANJM/adaptutor-agentathon.git`  
**Active Branch:** `main` (Production Core, Persistent Learner Model, Multi-Module Engine, Context-Enriched Remediation, Guided Practice)  
**Judge Entrypoint:** [`RUN.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/RUN.md) (`python run.py demo`)  

---

## 1. Executive Summary

Team uniCode engineered, tested, and validated **AdaptTutor**, an evidence-based adaptive computer science tutoring and remediation platform built atop the **Agentic Slice Kit** architectural spine. 

Traditional AI tutors suffer from two fatal failure modes:
1. **Unbounded, hallucinatory conversations** where the LLM grades quizzes incorrectly or repeats unhelpful explanations.
2. **One-size-fits-all pedagogy** where students with fundamentally different cognitive models (visual/analogical vs. mechanical/trace) receive identical explanations.

AdaptTutor solves this by implementing an **adaptive state machine** that strictly delegates reasoning:
- **Deterministic Python code** handles diagnostic quiz scoring, statistical multi-armed bandit style selection, retest evaluation, student mastery tracking, retest pool exhaustion detection, guided practice retry bounding, and human-in-the-loop instructor escalation.
- **The Large Language Model (OpenRouter)** is isolated to a single choke point (`slice/llm.py`) and used **exclusively** for high-quality pedagogical explanation generation, mistake diagnosis, and curriculum synthesis.

Across the development cycle, we moved from initial specifications to a fully deployed V1, upgraded to V2 with a persistent SQLite learner model, branched into topic-agnostic multi-course generation, perfected the prompt context pipeline, and incorporated four distinct cycles of real human testing and adversarial stress testing. The automated test suite grew from 0 to **125 fully automated unit and end-to-end scenario tests with 100% pass rate** and zero regressions.

---

## 2. Chronological Timeline: What Was Built

### Phase 1: Specifications & Architectural Invariants
- **Agent Specification (`AgentSpec-uniCode.md`)**: Formulated the formal specification declaring domain records, state transitions, budget fences, and human-in-the-loop policies.
- **Pre-Event Asset Declaration (`PRE-EVENT-ASSETS.md`)**: Certified standard open-source libraries (`pydantic`, `pytest`, `httpx`, `fastapi`, `uvicorn`) and initialized the Agentic Slice spine files.
- **Environment Diagnostics (`scripts/doctor.py`)**: Authored pre-flight diagnostic script verifying Python 3.10+, SQLite capabilities, required dependencies, and environment keys.

### Phase 2: AdaptTutor V1 Core Remediation Engine
- **State Machine Flow (`remediation/flow.py`)**: Built the deterministic 6-state remediation loop:
  $$\text{QUIZ} \longrightarrow \text{DIAGNOSE} \longrightarrow \text{SELECT} \longrightarrow \text{EXPLAIN} \longrightarrow \text{RETEST} \longrightarrow \text{EVALUATE}$$
- **Backward Loop & Escalation**: Implemented loop-bounds (`MAX_REVISIONS_PER_CONCEPT = 2`). If Attempt 1 fails, the system adapts backward to an alternate pedagogical style. If Attempt 2 fails, the system cleanly suspends into `AWAITING_EXPERT`.
- **Domain Records (`remediation/schema.py`)**: Defined typed Pydantic models for `QuizSubmission`, `Diagnosis`, `StyleSelection`, `ExplanationPayload`, `RetestResult`, `Outcome`, and `InstructorFlag`.
- **Data Decoupling**: Extracted hardcoded questions into validated, versioned JSON assets (`data/quiz.json`, `data/retest_questions.json`).

### Phase 3: Real LLM Integration & OpenRouter Resilience
- **Single Model Choke Point (`slice/llm.py`)**: Engineered the sole gateway for model interactions using OpenRouter (`openrouter/free` / `openai/gpt-4o-mini`).
- **Resilience Engineering**:
  - 3-stage exponential backoff retry loop (2s, 4s, 6s) targeting HTTP 429 rate limits and 502/503 gateway timeouts.
  - Automatic markdown code-fence stripping (`_strip_fence()`).
  - Automated single-pass self-repair (`_repair()`): Injects validation errors and JSON schema back to the model if formatting fails.
  - Zero-crash fallback to deterministic mock logic in case of complete external network failure.

### Phase 4: V2 Persistent Learner Model & Evidence-Based Selector
- **SQLite Persistence (`slice/store.py` & `remediation/learner.py`)**: Created dedicated tables (`learner_profiles` and `intervention_history`) to track student-specific and cohort-wide performance across sessions.
- **Mastery Math ($\alpha = 0.3$ EMA)**: Diagnostic errors initialize mastery to 25%; passing a retest awards +45% (capped at 95%); failing penalizes -15% (floored at 10%).
- **Multi-Armed Bandit Style Selector (`remediation/selector.py`)**: Formulated deterministic style scoring:
  $$\text{Score}(\text{style}) = 0.7 \times \text{StudentWinRate} + 0.3 \times \text{CohortWinRate}$$
  Ensures student historical learning preferences take precedence while benefiting from cohort wisdom when cold-starting.
- **Visual Adaptation UI Cards (`run.py`)**: Built rich ASCII terminal cards rendering Knowledge Gap alerts, style reasoning, dynamic progress bars (`[████░░░░░░]`), and post-retest delta evaluations.

### Phase 5: Human-in-the-Loop Web Dashboard (`web/expert.py`)
- **FastAPI Instructor Panel**: Real-time web portal (running on `http://127.0.0.1:8000`) displaying pending student escalation flags.
- **Student Roster (`/students`)**: Added comprehensive cohort dashboard displaying concept-by-concept mastery bars, weak/strong tags, and style efficacy metrics (win-rate per style).
- **Graceful Session Resumption**: When an instructor submits guidance, the suspended session automatically wakes from `AWAITING_EXPERT` and displays an instructor guidance banner in the student terminal.

### Phase 6: Topic-Agnostic Curriculum Engine
- Generalized AdaptTutor beyond Python recursion.
- Implemented modular curriculum loaders (`remediation/curriculum.py`) and packaged 4 complete course modules:
  - `python_recursion.json`: Week 6 Data Structures Recursion
  - `db_normalization.json`: CS330 Relational Normalization (1NF, 2NF, 3NF, BCNF)
  - `operating_systems_virtual.json`: CS340 Virtual Memory & Paging
  - `iot_mqtt.json`: IoT Messaging & QoS Levels
- Built an autonomous AI Curriculum Generator (`remediation/curriculum_generator.py`) capable of synthesizing a 4-concept curriculum with diagnostic and retest banks for any topic on demand.

### Phase 7: Context Enrichment & Personalized Explanations
- **Feedback Source**: Walkthrough 1 with **Roopa Varshni** ([`docs/evidence/walkthrough-1.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-1.md)).
- Overhauled `remediation/provider.py` and `remediation/flow.py` to inject full option breakdowns, explicit distractor tags (`[STUDENT'S WRONG CHOICE]`), concept learning objectives, student mastery %, and attempt history.
- Restructured `remediation/prompts/analogy.md` into a 3-part pedagogical scaffold (Physical Anchor $\to$ Misconception Hook $\to$ Resolution).
- **Commit**: `55c4908`.

### Phase 8: Mistake-Specific Failed Retest Feedback
- **Feedback Source**: Walkthrough 2 with **Jeeva S** ([`docs/evidence/walkthrough-2.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-2.md)).
- Created `remediation/feedback.py` and `RetestFeedback` model.
- When a student gets a retest wrong, the system pauses to diagnose the misconception behind their chosen option before transitioning to an alternate style.
- Terminal card `🔍 RETEST FEEDBACK — MISTAKE DIAGNOSIS` shows `Why your answer was wrong` (<50 words) and `What to remember` (<25 words).
- **Commit**: `6a9308c`.

### Phase 9: Clear Learning State & Immediate Goal Presentation
- **Feedback Source**: Walkthrough 3 with **Sripramod Y** ([`docs/evidence/walkthrough-3.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-3.md)).
- Created centralized pedagogical goal service in `remediation/goals.py`.
- Introduced `🎯 YOUR LEARNING STATE` card showing mastery, active approach, previous approach failure tag (`❌`), adaptation reason, and concrete goal.
- Introduced `✓ CONCEPT IMPROVED` card showing `old% ➔ new%`, delta percentage ($+45\%$), goal achieved confirmation, and next step pointer.
- **Commit**: `18cada7`.

### Phase 10: Retest Pool Exhaustion, Guided Practice & Fresh Retests
- **Feedback Source**: Stress Testing with **Vikram Dharshan** ([`docs/evidence/stress-test.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/stress-test.md)).
- Created question tracking service (`remediation/practice.py`) to prevent repeating retests while unused questions exist.
- When the curated retest pool is exhausted, the system transitions into **Guided Practice** (`⚠️ RETEST POOL EXHAUSTED`).
- Delivers 2–4 concept-specific reasoning steps with a strict **1-retry bound per step** with targeted hints, preventing infinite loops.
- Upon completion (`✓ GUIDED PRACTICE COMPLETE`), administers an independent **Fresh Retest** from a dedicated validation bank.
- Supports session interruption and crash resumption from SQLite event logs.
- **Commit**: `4654f9d`.

### Phase 11: Real Human Testing Declaration
- Formalized and published [`docs/USER_TESTING_DECLARATION.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/USER_TESTING_DECLARATION.md) certifying that all walkthroughs and stress testing were conducted with real engineering students via live interactive terminal sessions and standardized Google Forms surveys.

### Phase 12: Judge Execution Specification & Freeze Readiness
- Authored and verified [`RUN.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/RUN.md) containing the exact one-command turnkey demo (`python run.py demo`).
- Executed `python run.py demo` end-to-end with real OpenRouter LLM, confirming flawless execution across all 3 student personas (exit code 0).

---

## 3. Architectural Guardrails: The Agentic Slice Philosophy

AdaptTutor strictly abides by the **Agentic Slice** principle: *The LLM is a text generator, not an orchestrator, judge, or database.*

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

## 4. Verification, Testing & Health Metrics

The repository maintains an automated, comprehensive test suite with **125 passing tests** across 12 test suites with **100% pass rate**:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.4, pytest-9.0.2, pluggy-1.6.0
rootdir: adapt-tutor
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.11.0, timeout-2.4.0
collected 125 items

tests\test_budget.py ........                                            [  6%]
tests\test_callback.py .......                                           [ 12%]
tests\test_curriculum.py ......                                          [ 16%]
tests\test_feedback.py ......                                            [ 21%]
tests\test_goals.py ........                                             [ 28%]
tests\test_learner.py ........................                           [ 47%]
tests\test_practice.py .........                                         [ 54%]
tests\test_remediation.py ................                               [ 67%]
tests\test_runner.py ....                                                [ 70%]
tests\test_scenarios.py ........                                         [ 76%]
tests\test_selector.py ................                                  [ 89%]
tests\test_store.py .............                                        [100%]

============================ 125 passed in 18.42s =============================
```

### Coverage by Component:
1. **`test_budget.py` (8 tests)**: Token usage tracking, budget fence tripwires, call limits, and restart survival.
2. **`test_callback.py` (7 tests)**: Process suspension, state persistence in SQLite, write-once answering, and sweep timeout expiration.
3. **`test_curriculum.py` (6 tests)**: Dynamic module loading, multi-module scoring, AI curriculum generator, and end-to-end multi-module flow.
4. **`test_feedback.py` (6 tests)**: Mistake diagnosis generation, selected vs correct option extraction, adaptation continuation, and deterministic fallback.
5. **`test_goals.py` (8 tests)**: Predefined concept goals, achievement messages, dynamic synthesis, learning state card formatting, and retry context.
6. **`test_learner.py` (22 tests)**: Mastery initialization from quiz, retest updates, instructor override updates, concept classification (strong/weak), style efficacy tracking, and cross-session persistence.
7. **`test_practice.py` (9 tests)**: Question non-repetition, pool exhaustion detection, guided practice steps, 1-retry bound, history logging, fresh retest delivery, and crash resumption.
8. **`test_remediation.py` (16 tests)**: Scoring accuracy, case-insensitivity, style selection, question bank integrity, and enriched prompt message formatting.
9. **`test_runner.py` (4 tests)**: State transitions, maximum step bounding, and run state lifecycle.
10. **`test_scenarios.py` (8 tests)**: Full E2E student journeys (Priya, Ravi, Karthik), process crash and resume survival, and revision limits.
11. **`test_selector.py` (14 tests)**: Mathematical formula validation, history-driven selection, Attempt 2 style switching, and demo persona verification.
12. **`test_store.py` (13 tests)**: Append-only SQLite verification, version sequencing, run metadata, and cross-connection read consistency.

---

## 5. Verified Demo Personas

The system includes pre-seeded demonstration personas runnable live via `python run.py demo`:

| Persona | Demonstrated Cognitive Profile | Initial Knowledge Gap | Remediation Journey | Final State |
|---|---|---|---|---|
| **Ananya** | **Analogy Responder** (High visual/metaphorical affinity) | `call_stack` | Attempt 1: Receives **Analogy** $\to$ Retest: **PASS** | **RESOLVED** (Mastery: 25% $\to$ 70%) |
| **Bharat** | **Trace Responder** (Mechanical/step-by-step affinity) | `call_stack` | Attempt 1: Receives **Analogy** $\to$ Retest: **FAIL**<br>Mistake Diagnosis Card shown<br>Attempt 2: Switches to **Trace** $\to$ Retest: **PASS** | **RESOLVED** (Mastery: 25% $\to$ 10% $\to$ 55%) |
| **Karthik** | **Exhaustion & Guided Practice Candidate** | `call_stack` | Attempt 1: **Trace** $\to$ Retest: **FAIL**<br>Attempt 2: **Analogy** $\to$ Retest: **FAIL**<br>Pool Exhausted $\to$ **Guided Practice** (3 steps)<br>Fresh Retest: **PASS** | **RESOLVED** (Mastery: 25% $\to$ 10% $\to$ 55%) |

---

## 6. Current System Configuration

- **Active Branch**: `main` (feature branch `feat/topic-agnostic-curriculum` fully merged)
- **Default Database**: `run.db` (SQLite, append-only records)
- **Supported LLM Modes**:
  - `LLM_MODE=mock`: Deterministic zero-network mode for tests.
  - `LLM_MODE=real`: OpenRouter live generation (`openrouter/free` or specified model in `.env`).
- **Instructor Panel**: `python -m uvicorn web.expert:app --host 127.0.0.1 --port 8000`
- **Judge Execution Entrypoint**: [`RUN.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/RUN.md)

---

*Report prepared by Team uniCode (College of Engineering Guindy) for Agentathon 2026.*
