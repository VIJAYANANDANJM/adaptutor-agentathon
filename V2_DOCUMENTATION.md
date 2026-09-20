# AdaptTutor V2 — Complete Implementation Documentation

**Institution:** College of Engineering Guindy — Team uniCode  
**Base Commit:** `6ddee1c`  
**Current Status:** Production Ready (95/95 Tests Passing)  
**Date:** September 2026  

---

## 1. Executive Summary

AdaptTutor V2 upgrades the computer science tutoring system from a static state machine into an **evidence-based, adaptive remediation platform**. It addresses the challenge of student knowledge gaps by persistently tracking mastery in SQLite, dynamically selecting personalized instructional styles using a weighted statistical algorithm, visibly communicating adaptation decisions through terminal cards, and surfacing rich cohort insights via a web-based instructor dashboard.

### Core Upgrades at a Glance
- **Persistent Learner Model:** SQLite-backed concept-wise mastery (0–100%) and intervention logs across sessions.
- **Evidence-Based Adaptive Selector:** Deterministic selection ranking:
  $$\text{Score} = 0.7 \times \text{StudentRate} + 0.3 \times \text{CohortRate}$$
- **Visible Adaptation UI:** Rich terminal cards depicting Knowledge Gaps, Style Switching on failure, and Escalations with visual progress bars.
- **Enriched Instructor Dashboard:** Modern dark-mode web application featuring pending escalation queues and a complete student roster (`/students`).
- **Deterministic Demo Personas:** Turnkey verification command (`python run.py demo`) showcasing 3 distinct pedagogical journeys.
- **Zero LLM Grading / Selection:** Deterministic code exclusively handles style selection and answer evaluation.
- **Zero Regressions:** All 55 baseline tests pass, plus 40 new verification tests (95 total).

---

## 2. System Architecture & Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│                          DIAGNOSTIC QUIZ                               │
│              8 Questions Across 4 Core Concepts                        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        KNOWLEDGE GAP DIAGNOSIS                         │
│               LearnerModel initializes concept mastery                 │
│              Correct = 85%  |  Incorrect = 25% (Gap Found)             │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   ADAPTIVE INTERVENTION SELECTION                      │
│        Score = 0.7 * StudentWinRate + 0.3 * CohortWinRate              │
│          Attempt 1: Pick best style (Analogy vs. Trace)                │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      EXPLANATION & CURATED RETEST                      │
│              Retest question pulled from retest_questions.json         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
          [RETEST PASSED]                     [RETEST FAILED]
          Mastery += 45% (cap 95%)            Mastery -= 15% (floor 10%)
          Session Complete                    Attempt 1 failed?
                                                     │
                                                     ▼
                                      ┌─────────────────────────────┐
                                      │    BACKWARD ADAPTATION      │
                                      │ Switch to alternate style   │
                                      │ (Attempt 2 strictly != Att 1)│
                                      └──────────────┬──────────────┘
                                                     │
                                                     ▼
                                      ┌─────────────────────────────┐
                                      │       ATTEMPT 2 RETEST      │
                                      └──────────────┬──────────────┘
                                                     │
                                   ┌─────────────────┴─────────────────┐
                                   ▼                                   ▼
                            [RETEST PASSED]                     [RETEST FAILED]
                            Mastery += 45%                      Both styles exhausted
                            Session Complete                           │
                                                                       ▼
                                                        ┌─────────────────────────────┐
                                                        │  ESCALATE TO INSTRUCTOR     │
                                                        │  State: AWAITING_EXPERT     │
                                                        │  Dashboard flag generated   │
                                                        └─────────────────────────────┘
```

---

## 3. Detailed Component Breakdown

### 3.1 Persistent Learner Model
- **Files:** `slice/store.py`, `remediation/learner.py`
- **Database Schema:**
  - `learner_profiles`: Stores `(student_id, concept, mastery, updated_at)`.
  - `intervention_history`: Stores `(id, student_id, concept, style, attempt, passed, created_at)`.
- **Mastery Calculation Rules:**
  - Initial Diagnostic Quiz:
    - Correct answer $\to 0.85$ (85% mastery).
    - Incorrect answer $\to 0.25$ (25% mastery, flagged as knowledge gap).
  - Remediation Retest:
    - Passed $\to +0.45$ (+45%), capped at $0.95$ (95%).
    - Failed $\to -0.15$ (-15%), floored at $0.10$ (10%).
  - Human Instructor Guidance:
    - Resolved by instructor $\to +0.50$ (+50%), capped at $0.95$ (95%).
- **Concept Classification:**
  - Strong Concept: $\text{Mastery} \ge 0.75$ (75%).
  - Weak Concept: $\text{Mastery} \le 0.30$ (30%).

### 3.2 Evidence-Based Adaptive Selector
- **File:** `remediation/selector.py`
- **Scoring Function:**
  For each eligible explanation style $s \in \{\text{analogy}, \text{trace}\}$:
  $$\text{Score}(s) = 0.7 \times \text{Rate}_{\text{student}}(s) + 0.3 \times \text{Rate}_{\text{cohort}}(s)$$
  - $\text{Rate}_{\text{student}}(s)$: Student's historical pass rate with style $s$ across all concepts.
  - $\text{Rate}_{\text{cohort}}(s)$: Aggregate pass rate for style $s$ across all students in the database.
- **Rules & Guardrails:**
  - **Attempt 2 Never Repeats:** When Attempt 1 with style $s_1$ fails, $s_1$ is strictly excluded from Attempt 2.
  - **Fallback Hierarchy:**
    1. Weighted formula when student history exists.
    2. Cohort success rate if the student has no history.
    3. Default to `analogy` if no student or cohort data exists.
  - **Transparent Explanations:** Emits a deterministic reason string explaining why the style was chosen.

### 3.3 Visible Adaptation UI Cards
- **File:** `run.py`
- **UI Terminal Cards:**
  - **Knowledge Gap Card:** Shows detected concept gap, current mastery progress bar (`[████████░░]`), learner history, selected style, and decision reason.
  - **Retest Evaluation Card:** Displays `PASS ✅` or `FAILED ❌`, before/after mastery transition ($X\% \to Y\%$), and database persistence notice.
  - **Adaptation on Failure Card:** Explicitly alerts the user that Attempt 1 failed and shows the switch to the alternate style with justification.
  - **Escalation Card:** Announces suspension on human instructor when both automated styles fail.
  - **Windows Console Compatibility:** Automated stdout/stderr reconfiguration to UTF-8 to prevent Windows terminal `cp1252` encoding errors.

### 3.4 Enriched Instructor Dashboard
- **File:** `web/expert.py`
- **Routes & Capabilities:**
  - `GET /`: Escalations queue showing pending student flags with student ID, concept, visual mastery bar, styles already tried, wrong answers submitted, and remaining token budget.
  - `GET /q/{qid}`: Human-in-the-loop response form where instructors submit hints or guidance.
  - `POST /q/{qid}`: Submits guidance, updates the student's mastery by $+50\%$, records the intervention, and resumes the suspended state machine.
  - `GET /students`: Student Roster dashboard listing all tracked students, average mastery, concept-wise progress bars, `Strong`/`Weak` tags, and style efficacy statistics.

### 3.5 Deterministic Demo Personas
- **Files:** `remediation/stub.py`, `scripts/seed_demo.py`
- **Pre-configured Personas:**
  1. **Ananya (`ananya_analogy`):**
     - Pre-seeded with 2 Analogy wins (100% win rate).
     - Adaptive selector chooses **Analogy** for `call_stack`.
     - Passes retest on Attempt 1. Mastery advances: $25\% \to 70\%$.
  2. **Bharat (`bharat_trace`):**
     - Pre-seeded with 1 Analogy loss and 2 Trace wins (100% Trace win rate).
     - Adaptive selector chooses **Trace** for `call_stack`.
     - Passes retest on Attempt 1. Mastery advances: $25\% \to 70\%$.
  3. **Karthik (`karthik_stuck`):**
     - Clean slate (no prior history).
     - Receives cohort default (Trace) on Attempt 1 $\to$ Fails.
     - System adapts and switches to Analogy on Attempt 2 $\to$ Fails.
     - Cleanly escalates to instructor dashboard.

---

## 4. Repository File Layout

```
adapt-tutor/
├── data/
│   ├── quiz.json                   # 8-question diagnostic quiz
│   └── retest_questions.json       # Curated retest question bank
├── remediation/
│   ├── flow.py                     # Remediation state machine handlers
│   ├── learner.py                  # LearnerModel class & mastery rules [NEW]
│   ├── provider.py                 # Real LLM explanation provider
│   ├── questions.py                # Curriculum loaders and validation
│   ├── schema.py                   # Pydantic schemas
│   ├── selector.py                 # Weighted adaptive style selector [NEW]
│   └── stub.py                     # Persona answers and test stubs [MODIFIED]
├── scripts/
│   ├── doctor.py                   # Environment & dependency verification
│   └── seed_demo.py                # Demo persona database seeder [NEW]
├── slice/
│   ├── budget.py                   # Token and attempt tracking
│   ├── callback.py                 # Human escalation callbacks
│   ├── config.py                   # Configuration and settings
│   ├── llm.py                      # OpenRouter client integration
│   ├── records.py                  # Core data records & enums
│   ├── runner.py                   # Deterministic state machine runner
│   └── store.py                    # Append-only SQLite store + Learner tables [MODIFIED]
├── tests/
│   ├── test_budget.py              # Budget fence tests (8 tests)
│   ├── test_callback.py            # Human escalation tests (7 tests)
│   ├── test_learner.py             # LearnerModel tests (22 tests) [NEW]
│   ├── test_remediation.py         # Quiz, selector & question tests (15 tests)
│   ├── test_runner.py              # Runner & step tests (4 tests)
│   ├── test_scenarios.py           # E2E student scenario tests (8 tests)
│   ├── test_selector.py            # Adaptive selector tests (14 tests) [NEW]
│   └── test_store.py               # SQLite store invariant tests (13 tests)
├── web/
│   └── expert.py                   # FastAPI instructor dashboard [MODIFIED]
├── run.py                          # CLI entrypoint with UI cards & demo [MODIFIED]
├── STATE.md                        # Project milestone tracker
└── V2_DOCUMENTATION.md             # This document
```

---

## 5. Verification & Testing

### 5.1 Test Suite Breakdown (95 Tests)
```powershell
python -m pytest -v
```
All 95 unit and integration tests pass:
- **`tests/test_learner.py` (22 tests):** Quiz initialization, retest increment/decrement rules, instructor bonuses, caps/floors, concept classification, style win rates, and cross-restart persistence.
- **`tests/test_selector.py` (14 tests):** Weighting formula ($0.7 / 0.3$), differential selection for identical gaps, Attempt 2 non-repetition, fallback hierarchy, demo persona selections, and reason string validation.
- **`tests/test_store.py` (13 tests):** Append-only triggers, versioning, counters, question storage, and SQLite persistence.
- **`tests/test_remediation.py` (15 tests):** Quiz scoring, question bank validity, real LLM providers.
- **`tests/test_scenarios.py` (8 tests):** Priya, Ravi, and Karthik end-to-end user journeys, revision limits, and process interruption resilience.
- **`tests/test_budget.py` (8 tests):** Token budgets, attempt fences, restart survival.
- **`tests/test_callback.py` (7 tests):** Escalation suspension, instructor answering, timeouts, and sweeps.
- **`tests/test_runner.py` (4 tests):** Runner loop, terminal states, max step fences.

### 5.2 Environment Diagnostics
```powershell
python scripts/doctor.py
```
Output:
```text
AdaptTutor doctor
------------------------------------------------------------
[  ok  ] Python 3.13.4
[  ok  ] pydantic 2.11.9
[  ok  ] pytest 9.0.2
[  ok  ] httpx 0.28.1
[  ok  ] fastapi 0.141.1
[  ok  ] uvicorn 0.53.0
[  ok  ] .env found
[  ok  ] LLM_MODE=real
[  ok  ] OPENROUTER_API_KEY is set
[  ok  ] SQLite works
[  ok  ] import slice.records
[  ok  ] import slice.store
[  ok  ] import slice.runner
[  ok  ] import slice.budget
[  ok  ] import slice.callback
[  ok  ] import slice.config
[  ok  ] import remediation.schema
[  ok  ] import remediation.questions
[  ok  ] import remediation.provider
[  ok  ] import remediation.flow
[  ok  ] import remediation.stub
------------------------------------------------------------
all clear — environment ready
```

---

## 6. How to Run & Verify

### 6.1 Execute the Demo
Runs all 3 deterministic personas with visible adaptation cards:
```powershell
python run.py demo
```

### 6.2 Start the Instructor Dashboard
Launches the web interface on port 8000:
```powershell
python -m uvicorn web.expert:app --host 127.0.0.1 --port 8000
```
- **Escalation Queue:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Student Roster & Mastery:** [http://127.0.0.1:8000/students](http://127.0.0.1:8000/students)

### 6.3 Seed or Reset Demo Data
```powershell
python scripts/seed_demo.py          # Pre-seeds demo student histories
python scripts/seed_demo.py --clean  # Clears demo records from database
```

### 6.4 Start an Interactive Session
Start an interactive student session:
```powershell
python run.py session <student_id>
```
