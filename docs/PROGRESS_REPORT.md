# AdaptTutor — Comprehensive Project Progress Report

**Project:** AdaptTutor (Adaptive Remediation & Intelligent Tutoring System)  
**Institution:** College of Engineering Guindy — Team uniCode  
**Event:** Agentathon 2026  
**Date:** September 19, 2026  
**Repository:** `https://github.com/VIJAYANANDANJM/adaptutor-agentathon.git`  
**Active Branches:**  
- `main` (Production Core, Persistent Learner Model, Enriched Context Remediation — Commit `55c4908`)
- `feat/topic-agnostic-curriculum` (Multi-Module Course Engine & AI Curriculum Generator — Commit `4088da4`)

---

## 1. Executive Summary

Today, Team uniCode engineered, tested, and validated **AdaptTutor**, an evidence-based adaptive computer science tutoring and remediation platform built atop the **Agentic Slice Kit** architectural spine. 

Traditional AI tutors suffer from two fatal failure modes:
1. **Unbounded, hallucinatory conversations** where the LLM grades quizzes incorrectly or repeats unhelpful explanations.
2. **One-size-fits-all pedagogy** where students with fundamentally different cognitive models (visual/analogical vs. mechanical/trace) receive identical explanations.

AdaptTutor solves this by implementing an **adaptive state machine** that strictly delegates reasoning:
- **Deterministic Python code** handles diagnostic quiz scoring, statistical multi-armed bandit style selection, retest evaluation, student mastery tracking, and human-in-the-loop instructor escalation.
- **The Large Language Model (OpenRouter)** is isolated to a single choke point (`slice/llm.py`) and used **exclusively** for high-quality pedagogical explanation generation and curriculum synthesis.

Across the development cycle today, we moved from initial specifications to a fully deployed V1, upgraded to V2 with a persistent SQLite learner model, branched into topic-agnostic multi-course generation, and perfected the prompt context pipeline. The test suite grew from 0 to **97 fully automated unit and end-to-end scenario tests with 100% pass rate** and zero regressions.

---

## 2. Chronological Timeline: What Was Built Today

### Phase 1: Specifications & Architectural Invariants
- **Agent Specification (`AgentSpec-uniCode.md`)**: Formulated the formal specification declaring domain records, state transitions, budget fences, and human-in-the-loop policies.
- **Pre-Event Asset Declaration (`PRE-EVENT-ASSETS.md`)**: Certified standard open-source libraries (`pydantic`, `pytest`, `httpx`, `fastapi`, `uvicorn`) and initialized the Agentic Slice spine files.
- **Environment Diagnostics (`scripts/doctor.py`)**: Authored pre-flight diagnostic script verifying Python 3.10+, SQLite capabilities, required dependencies, and environment keys.

### Phase 2: AdaptTutor V1 Core Remediation Engine
- **State Machine Flow (`remediation/flow.py`)**: Built the deterministic 6-state remediation loop:
  $$\text{QUIZ} \longrightarrow \text{DIAGNOSE} \longrightarrow \text{SELECT} \longrightarrow \text{EXPLAIN} \longrightarrow \text{RETEST} \longrightarrow \text{EVALUATE}$$
- **Backward Loop & Escalation**: Implemented loop-bounds (`MAX_REVISIONS_PER_CONCEPT = 2`). If Attempt 1 fails, the system adapts backward to an alternate pedagogical style. If Attempt 2 fails, the system cleanly suspends into `AWAITING_EXPERT`.
- **Domain Records (`remediation/schema.py`)**: Defined typed Pydantic models for `QuizSubmission`, `Diagnosis`, `StyleSelection`, `ExplanationPayload`, `RetestResult`, `Outcome`, and `InstructorFlag`.
- **Data Decoupling**: Extracted hardcoded questions into validated, versioned JSON assets:
  - `data/quiz.json`: 8-question diagnostic assessment (2 questions per concept across 4 recursion concepts).
  - `data/retest_questions.json`: Independent retest banks for Attempt 1 and Attempt 2 variants.

### Phase 3: Real LLM Integration & OpenRouter Resilience
- **Single Model Choke Point (`slice/llm.py`)**: Engineered the sole gateway for model interactions using OpenRouter (`openrouter/free` / `openai/gpt-4o-mini`).
- **Resilience Engineering**:
  - 3-stage exponential backoff retry loop (2s, 4s, 6s) targeting HTTP 429 rate limits and 502/503 gateway timeouts.
  - Automatic markdown code-fence stripping (`_strip_fence()`).
  - Automated single-pass self-repair (`_repair()`): Injects validation errors and JSON schema back to the model if formatting fails.
  - Zero-crash fallback to `MockExplanationProvider` in case of complete external network failure.

### Phase 4: V2 Persistent Learner Model & Evidence-Based Selector
- **SQLite Persistence (`slice/store.py` & `remediation/learner.py`)**: Created dedicated tables (`learner_profiles` and `intervention_history`) to track student-specific and cohort-wide performance across sessions.
- **Mastery Math ($\alpha = 0.3$ EMA)**: Diagnostic errors initialize mastery to 25%; passing a retest awards +45% (capped at 95%); failing penalizes -15% (floored at 10%).
- **Multi-Armed Bandit Style Selector (`remediation/selector.py`)**: Formulated deterministic style scoring:
  $$\text{Score}(\text{style}) = 0.7 \times \text{StudentWinRate} + 0.3 \times \text{CohortWinRate}$$
  Ensures student historical learning preferences take precedence while benefiting from cohort wisdom when cold-starting.
- **Visual Adaptation UI Cards (`run.py`)**: Built rich ASCII terminal cards rendering Knowledge Gap alerts, style reasoning, dynamic progress bars (`[████░░░░░░]`), and post-retest delta evaluations.

### Phase 5: Human-in-the-Loop Web Dashboard (`web/expert.py`)
- **FastAPI Instructor Panel**: Real-time web portal (running on `http://127.0.0.1:8000` / `8001`) displaying pending student escalation flags.
- **Student Roster (`/students`)**: Added comprehensive cohort dashboard displaying concept-by-concept mastery bars, weak/strong tags, and style efficacy metrics (win-rate per style).
- **Graceful Session Resumption**: When an instructor submits guidance, the suspended session automatically wakes from `AWAITING_EXPERT` and displays an instructor guidance banner in the student terminal.

### Phase 6: Topic-Agnostic Engine (`feat/topic-agnostic-curriculum` Branch)
- Created a dedicated feature branch to generalize AdaptTutor beyond Python recursion.
- Implemented modular curriculum loaders (`remediation/curriculum.py`) and packaged 3 complete course modules (`python_recursion`, `db_normalization`, `operating_systems_virtual`).
- Built an autonomous AI Curriculum Generator (`remediation/curriculum_generator.py`) capable of synthesizing a 4-concept curriculum with diagnostic and retest banks for any topic on demand.

### Phase 7: Context Enrichment & Pedagogical Prompts (`main` Branch)
- Diagnosed and resolved the "prompt blind spot" where the LLM received single-letter choices (`'b'`, `'a'`) without option text.
- Overhauled `remediation/provider.py` and `remediation/flow.py` to inject full option breakdowns, explicit distractor tags (`[STUDENT'S WRONG CHOICE]`), concept learning objectives, student mastery %, and attempt history.
- Restructured `remediation/prompts/analogy.md` and `remediation/prompts/trace.md` into rigorous 3-part pedagogical frameworks.

---

## 3. Detailed Branch Analysis

### Branch 1: `main` (Production Core & Context Enrichment)
**Commit:** `55c4908`  
**Focus:** Production-ready stability, persistent learner modeling, and context-enriched remediation explanations.

#### Key Highlights on `main`:
1. **Enriched Prompt Pipeline**:
   - In `handle_explain()`, the tutor resolves the missed question's complete options dictionary.
   - The user prompt sent to the LLM explicitly tags each choice:
     ```text
     [A] 4 frames  <-- [STUDENT'S WRONG CHOICE]
     [B] 5 frames  <-- [CORRECT ANSWER]
     [C] 3 frames
     [D] 1 frame
     ```
   - Injects student knowledge profile: `Remediation Attempt: 2 of 2 (Previous 'trace' style failed)`, `Current Concept Mastery: 25%`.
2. **Pedagogical 3-Part Analogy Scaffold (`remediation/prompts/analogy.md`)**:
   - **Step 1: Physical Anchor**: Concrete real-world system (cafeteria trays, nesting dolls, relay race runners).
   - **Step 2: Misconception Anchor**: Specifically map the student's chosen wrong answer to the physical failure point (e.g. forgetting the base-case bottom tray).
   - **Step 3: Solution Emergence**: Show how the correct answer naturally follows.
   - Forbids code blocks or pseudocode; enforces <180 words.
3. **Execution Trace Scaffold (`remediation/prompts/trace.md`)**:
   - Requires formatted markdown tables / numbered call sequences.
   - Explicitly pinpoints where the student's reasoning diverged from the stack frame unwinding.
4. **Test Suite**: 97 automated tests passing in ~3.2 seconds.

---

### Branch 2: `feat/topic-agnostic-curriculum` (Generalization & AI Generator)
**Commit:** `4088da4` (branched off `92f193c`)  
**Focus:** Generalizing AdaptTutor from a single-course recursion tutor into an open multi-course adaptive platform.

#### Key Highlights on `feat/topic-agnostic-curriculum`:
1. **Modular Curriculum Architecture (`remediation/curriculum.py`)**:
   - Replaced fixed recursion lookups with a dynamic `CurriculumModule` registry.
   - Modules are stored as self-contained, validated JSON packages in `data/modules/`.
   - Each module defines:
     - `module_id`, `title`, `description`
     - 4 sub-concepts with human-readable display names
     - Available explanation styles & topic-specific style instructions
     - 8-question diagnostic quiz
     - Independent Attempt 1 and Attempt 2 retest banks
2. **Pre-Packaged Subject Modules**:
   - `python_recursion.json`: CS310 — Recursion & Stack Frames (Base Case, Recursive Step, Call Stack, Return Propagation).
   - `db_normalization.json`: CS330 — Relational Database Normalization (1NF, 2NF, 3NF, BCNF).
   - `operating_systems_virtual.json`: CS340 — Operating Systems Memory Management (Page Tables, TLB, Virtual Addresses, Page Faults).
3. **AI Curriculum Generator (`remediation/curriculum_generator.py`)**:
   - Allows instructors to generate a brand new verified course module for any topic:
     ```bash
     python run.py generate-curriculum "Graph Algorithms" "CS301 university course"
     ```
   - Uses OpenRouter with structured Pydantic schema enforcement (`GeneratedModuleSchema`).
   - Includes deterministic offline fallback template generation for mock/offline use.
4. **Interactive CLI Course Catalog (`run.py`)**:
   - `python run.py modules`: Lists all installed curriculum packages and concept counts.
   - Interactive topic selection menu on `python run.py session <student_id>` displaying the student's historical mastery per subject.
5. **Multi-Module Instructor Web Dashboard (`web/expert.py`)**:
   - Displays active course module badges and routes escalations with subject-specific context.

---

## 4. Technical Challenges Faced & Engineering Solutions

| # | Challenge | Root Cause | Engineering Solution Implemented |
|---|---|---|---|
| **1** | **Windows Terminal Encoding & Subprocess Execution** | Windows default CP1252 codepage caused `UnicodeEncodeError` on Unicode characters (`█`, `→`, `✓`); `os.execvp` failed to resolve Python executable. | Reconfigured `sys.stdout` and `sys.stderr` to UTF-8 with error replacement; replaced `os.execvp` with explicit `subprocess.run` across CLI handlers. |
| **2** | **OpenRouter API Reliability & Rate Limits** | Free tier endpoints occasionally return HTTP 429 (rate limits) or transient HTTP 502/503 pauses. | Built a 3-tier exponential backoff retry loop (2s, 4s, 6s) with a 120s timeout in `slice/llm.py`; added resilient automatic fallback to `MockExplanationProvider` to prevent session abortion. |
| **3** | **LLM Formatting Deviations (Markdown Fences)** | LLMs often wrap JSON in ````json ... ```` fences or prepend conversational pleasantries, violating strict JSON parsing. | Implemented `_strip_fence()` regex/brace extractors and an automated single-pass `_repair()` function that reflects the Pydantic validation error back to the model. |
| **4** | **Prompt "Blind Spot" (Loss of Misconception Context)** | The LLM originally received only `'b'` as wrong answer and `'a'` as correct answer without option text, forcing the model to guess what distractor was chosen. | Enriched `handle_explain` and `provider.py` to extract and send full option dictionaries, explicitly tagging `[STUDENT'S WRONG CHOICE]` and `[CORRECT ANSWER]` alongside concept display names. |
| **5** | **FastAPI Multipart Form Dependency** | `web/expert.py` threw errors when parsing instructor form submissions if `python-multipart` was absent in minimal Python environments. | Reworked form ingestion in FastAPI handlers using direct `await request.form()` parsing, eliminating rigid dependency requirements. |
| **6** | **Port Binding Conflicts** | Background uvicorn processes holding port 8000 during rapid testing cycles, causing `[Errno 10048] address already in use`. | Utilized PowerShell socket diagnostics (`Get-NetTCPConnection`), cleaned stale tasks, and made web ports easily configurable (8000/8001). |
| **7** | **LLM Boundary Invariants (Preventing Overreach)** | Risk of LLMs hallucinating test scores, inventing nonexistent questions, or picking styles arbitrarily. | Enforced strict architectural separation: zero LLM grading (all evaluated against verified JSON keys) and zero LLM style selection (calculated via deterministic statistical formulas). |

---

## 5. Architectural Guardrails: The Agentic Slice Philosophy

AdaptTutor strictly abides by the **Agentic Slice** principle: *The LLM is a text generator, not an orchestrator, judge, or database.*

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DETERMINISTIC PYTHON LAYER                      │
│                                                                        │
│  • Diagnostic Quiz Scoring     ──> Exact string match vs. answer_key   │
│  • Knowledge Gap Diagnosis     ──> Set-difference math                 │
│  • Style Selection Algorithm   ──> 0.7 * StudentRate + 0.3 * CohortRate│
│  • Revision Loop Fencing       ──> Hard limit: MAX_REVISIONS = 2       │
│  • Retest Evaluation           ──> Exact match vs. verified retest key │
│  • Mastery Tracking (EMA)      ──> SQLite learner_profiles             │
│  • Human Escalation Callback   ──> State transition: AWAITING_EXPERT   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                     Only Explanation Generation
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         ISOLATED LLM LAYER                             │
│                                                                        │
│  • slice/llm.py Choke Point    ──> Single complete() function          │
│  • Pedagogical Text Synthesis  ──> Generate Analogy or Trace text      │
│  • Pydantic Schema Validation  ──> ExplanationPayload contract         │
│  • Single-Pass Self Repair     ──> Fixed schema reflection on failure  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Verification, Testing & Health Metrics

The repository maintains an automated, comprehensive test suite with **97 passing tests** across 8 test suites:

```text
tests\test_budget.py ........                                            [  8%]
tests\test_callback.py .......                                           [ 15%]
tests\test_learner.py ........................                           [ 40%]
tests\test_remediation.py .................                              [ 57%]
tests\test_runner.py ....                                                [ 61%]
tests\test_scenarios.py ........                                         [ 70%]
tests\test_selector.py ................                                  [ 86%]
tests\test_store.py .............                                        [100%]
============================= 97 passed in 3.20s ==============================
```

### Coverage by Component:
1. **`test_budget.py` (8 tests)**: Token usage tracking, budget fence tripwires, call limits, and restart survival.
2. **`test_callback.py` (7 tests)**: Process suspension, state persistence in SQLite, write-once answering, and sweep timeout expiration.
3. **`test_learner.py` (22 tests)**: Mastery initialization from quiz, retest updates, instructor override updates, concept classification (strong/weak), style efficacy tracking, and cross-session persistence.
4. **`test_remediation.py` (17 tests)**: Scoring accuracy, case-insensitivity, style selection, mock provider execution, question bank integrity, and enriched prompt message formatting.
5. **`test_runner.py` (4 tests)**: State transitions, maximum step bounding, and run state lifecycle.
6. **`test_scenarios.py` (8 tests)**: Full E2E student journeys (Priya, Ravi, Karthik), process crash and resume survival, and revision limits.
7. **`test_selector.py` (14 tests)**: Mathematical formula validation, history-driven selection, Attempt 2 style switching, and demo persona verification.
8. **`test_store.py` (13 tests)**: Append-only SQLite verification, version sequencing, run metadata, and cross-connection read consistency.

---

## 7. Deterministic Demo Personas

The system includes pre-seeded demonstration personas runnable in zero-network mock mode or real LLM mode via `python run.py demo`:

| Persona | Demonstrated Cognitive Profile | Initial Knowledge Gap | Remediation Journey | Final State |
|---|---|---|---|---|
| **Priya** | **Analogy Responder** (High visual/metaphorical affinity) | `call_stack` | Attempt 1: Receives **Analogy** $\to$ Retest: **PASS** | **RESOLVED** (Mastery: 25% $\to$ 70%) |
| **Ravi** | **Trace Responder** (Mechanical/step-by-step affinity) | `return_propagation` | Attempt 1: Receives **Analogy** $\to$ Retest: **FAIL**<br>Attempt 2: Switches to **Trace** $\to$ Retest: **PASS** | **RESOLVED** (Mastery: 25% $\to$ 10% $\to$ 55%) |
| **Karthik** | **Escalation Candidate** (Complex conceptual block) | `base_case` | Attempt 1: Receives **Analogy** $\to$ Retest: **FAIL**<br>Attempt 2: Receives **Trace** $\to$ Retest: **FAIL** | **AWAITING_EXPERT** (Escalated to Instructor Dashboard) |

---

## 8. Current System Configuration

- **Active Branch**: `main`
- **Feature Branch**: `feat/topic-agnostic-curriculum`
- **Default Database**: `run.db` (SQLite, append-only records)
- **Supported LLM Modes**:
  - `LLM_MODE=mock`: Deterministic zero-network mode for tests and offline demos.
  - `LLM_MODE=real`: OpenRouter live generation (`openrouter/free` or specified model in `.env`).
- **Instructor Panel**: `python -m uvicorn web.expert:app --host 127.0.0.1 --port 8000`

---

## 9. Next Steps & Roadmap

1. **Branch Consolidation**: Merge `feat/topic-agnostic-curriculum` into `main` so that the enriched prompt engine automatically applies to all dynamic AI-generated modules.
2. **Multi-Modal Explanations**: Integrate dynamic SVG call-stack diagram generation for the `trace` style.
3. **LMS Interoperability**: Implement an LTI 1.3 gateway to export student mastery profiles to Canvas and Moodle.

---

*Report prepared by Team uniCode (College of Engineering Guindy) for Agentathon 2026.*
