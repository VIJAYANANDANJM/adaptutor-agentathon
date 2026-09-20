# AdaptTutor

**Evidence-Based Adaptive Tutoring & Remediation Platform for Computer Science**

*Team uniCode | B.E. Computer Science and Engineering, College of Engineering Guindy (CEG), Anna University*  
*Agentathon 2026*

---

## What It Does

AdaptTutor diagnoses individual student misconceptions in computer science concepts and delivers targeted, adaptive remediation. Unlike traditional conversational tutors that suffer from hallucinations, scoring errors, or repetitive explanations, AdaptTutor separates concerns:
- **Deterministic Python Engine**: Handles diagnostic scoring, statistical style selection, retest evaluation, EMA mastery calculation, loop bounding, and escalation tripwires.
- **Isolated LLM Choke Point**: Uses the Large Language Model via OpenRouter (`slice/llm.py`) exclusively for high-fidelity pedagogical explanation generation and curriculum synthesis.

### Key Capabilities

1. **Fine-Grained Diagnosis**: Pinpoints exact knowledge gaps from diagnostic assessments across multiple concepts.
2. **Context-Enriched Explanations**: Injects student wrong choices (`[STUDENT'S WRONG CHOICE]`), learning objectives, and 3-part structured analogy scaffolding into LLM prompts.
3. **Evidence-Based Style Selection**: Multi-armed bandit ranker prioritizing student-specific learning history while benefiting from cohort wisdom ($0.7 \times \text{StudentRate} + 0.3 \times \text{CohortRate}$).
4. **Transparent Learning State**: Real-time terminal cards (`🎯 YOUR LEARNING STATE`, `✓ CONCEPT IMPROVED`) displaying mastery progress bars, previous approach results, and concrete learning objectives.
5. **Mistake-Specific Retest Feedback**: When a retest fails, immediately diagnoses *why* the student's chosen option was incorrect before pivoting to an alternate teaching style.
6. **Retest Exhaustion → Guided Practice → Fresh Retest**: When curated retests are exhausted, transitions into concept-specific, 2–4 step Guided Practice bounded by a strict 1-retry limit, followed by an independent Fresh Retest.
7. **Topic-Agnostic Curriculum Engine**: Built-in support for Python Recursion, Relational Database Normalization, OS Virtual Memory, and IoT MQTT, plus an autonomous AI Curriculum Generator (`python run.py generate-curriculum`).
8. **Human-in-the-Loop Web Portal**: Real-time instructor web dashboard (`web/expert.py`) tracking student mastery rosters, concept weakness tags, and escalation flags.

---

## Quick Start for Judges

To run the live demo that exercises the full system, refer to [`RUN.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/RUN.md):

```bash
# 1. Ensure OPENROUTER_API_KEY is configured (or loaded from .env)
export OPENROUTER_API_KEY="your-openrouter-api-key"

# 2. Run the live 3-persona demo (Ananya, Bharat, Karthik)
python run.py demo
```

### Alternative Commands

```bash
# Run interactive student remediation session
python run.py session student_demo

# Run pre-flight environment diagnostics
python run.py doctor

# Run full automated test suite (125 tests, zero network needed)
python -m pytest

# Start the instructor web dashboard (view at http://127.0.0.1:8000/students)
python -m uvicorn web.expert:app --host 127.0.0.1 --port 8000
```

---

## Architecture

```
adapt-tutor/
├── slice/                          # Core Agentic Slice Architecture
│   ├── records.py                  # RunState, Version, Question models
│   ├── store.py                    # Append-only SQLite persistence with triggers
│   ├── runner.py                   # Deterministic state machine runner
│   ├── llm.py                      # Single LLM choke point with retry & self-repair
│   ├── budget.py                   # Token and attempt fences
│   ├── callback.py                 # Human-in-the-loop process suspension
│   └── config.py                   # Environment settings & configuration
│
├── remediation/                    # Remediation Domain & Pedagogical Logic
│   ├── schema.py                   # Pydantic schemas (Diagnosis, Feedback, GuidedStep, etc.)
│   ├── flow.py                     # Remediation state machine lifecycle
│   ├── provider.py                 # Context-enriched LLM explanation assembly
│   ├── feedback.py                 # Mistake-specific failed retest diagnosis service
│   ├── goals.py                    # Centralized learning goal & achievement service
│   ├── practice.py                 # Retest pool exhaustion, guided practice & fresh retests
│   ├── curriculum.py               # Topic-agnostic course loader
│   ├── curriculum_generator.py     # AI curriculum generator using OpenRouter
│   ├── learner.py                  # Persistent LearnerModel (EMA mastery tracking)
│   ├── selector.py                 # Multi-armed bandit style selection algorithm
│   ├── questions.py                # Base curriculum questions and answer keys
│   ├── stub.py                     # Persona responses for deterministic testing & demos
│   └── prompts/                    # Analogy and trace prompt templates
│
├── data/
│   ├── modules/                    # Course packages (Recursion, Normalization, OS, MQTT)
│   ├── quiz.json                   # Diagnostic assessment questions
│   └── retest_questions.json       # Curated retest question pool
│
├── docs/                           # Documentation & Human Evaluation Evidence
│   ├── PROGRESS_REPORT.md          # Comprehensive chronological progress report
│   ├── USER_TESTING_DECLARATION.md # Formal declaration of real human testing via Google Forms
│   └── evidence/                   # Tester walkthroughs & stress testing reports
│       ├── walkthrough-1.md        # Roopa Varshni (personalized explanations)
│       ├── walkthrough-2.md        # Jeeva S (mistake-specific retest feedback)
│       ├── walkthrough-3.md        # Sripramod Y (clear learning state & goals)
│       ├── stress-test.md          # Vikram Dharshan (pool exhaustion & guided practice)
│       ├── design-rationale.md     # Architectural, pedagogical & math decisions
│       └── DECLARATION.md          # Certification of user testing
│
├── web/
│   └── expert.py                   # FastAPI instructor web portal & student roster
│
├── scripts/
│   ├── doctor.py                   # Pre-flight environment diagnostics
│   └── seed_demo.py                # Pre-seeds demo persona intervention histories
│
├── tests/                          # Automated test suites (125 tests, 100% pass)
├── RUN.md                          # Judge quick-start execution guide
└── run.py                          # CLI entrypoint for sessions, demos, and modules
```

---

## Remediation State Machine

```text
               ┌────────────────────────┐
               │    DIAGNOSTIC QUIZ     │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │   DIAGNOSE GAPS        │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │ 🎯 YOUR LEARNING STATE │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │  SELECT & EXPLAIN      │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │      RETEST Q1         │
               └───────────┬────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
       [PASSED ✓]                    [FAILED ❌]
  Mastery += 45%                          │
  ✓ CONCEPT IMPROVED                      ▼
  Next Gap / Complete        ┌────────────────────────┐
                             │  🔍 RETEST FEEDBACK    │
                             │   (Mistake Diagnosis)  │
                             └────────────┬───────────┘
                                          │
            ┌─────────────────────────────┴─────────────────────────────┐
            ▼                                                           ▼
  [Unused Retests Available]                               [Retest Pool Exhausted]
            │                                                           │
            ▼                                                           ▼
  Switch Teaching Style                                       ⚠️ RETEST POOL EXHAUSTED
  (Analogy ↔ Trace)                                                    │
            │                                                           ▼
            ▼                                                 🧭 GUIDED PRACTICE
        Retest Q2                                             (2–4 micro-steps,
            │                                                 1-retry limit per step)
     (Pass or Fail)                                                    │
                                                                        ▼
                                                             ✓ GUIDED PRACTICE COMPLETE
                                                                        │
                                                                        ▼
                                                             🎯 FRESH INDEPENDENT RETEST
                                                                        │
                                                       ┌────────────────┴────────────────┐
                                                       ▼                                 ▼
                                                  [PASSED ✓]                        [FAILED ❌]
                                              ✓ CONCEPT IMPROVED                         │
                                              Next Gap / Complete                        ▼
                                                                                AWAITING_EXPERT
                                                                            (Escalate to Instructor)
```

---

## Verification & Test Health

The repository maintains an automated, comprehensive test suite with **125 passing tests** across 12 test suites with **100% pass rate** and zero regressions:

```bash
python -m pytest -v
```

| Test Suite | Tests | Component Covered |
|---|---|---|
| [`test_budget.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_budget.py) | 8 | Token usage tracking, budget fences, attempt limits, restart survival |
| [`test_callback.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_callback.py) | 7 | Process suspension, state persistence in SQLite, write-once answering, timeout |
| [`test_curriculum.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_curriculum.py) | 6 | Dynamic curriculum loader, multi-course scoring, AI curriculum generator |
| [`test_feedback.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_feedback.py) | 6 | Mistake-specific failed retest feedback, option extraction, deterministic fallback |
| [`test_goals.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_goals.py) | 8 | Learning goal service, state & improvement cards, retry context |
| [`test_learner.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_learner.py) | 22 | Persistent LearnerModel, EMA mastery math, classification, style win-rate |
| [`test_practice.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_practice.py) | 9 | Pool exhaustion detection, guided practice steps, 1-retry bound, fresh retests, resumption |
| [`test_remediation.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_remediation.py) | 16 | Scoring accuracy, style selection, question bank integrity, enriched prompts |
| [`test_runner.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_runner.py) | 4 | State machine transitions, max step bounding, run state lifecycle |
| [`test_scenarios.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_scenarios.py) | 8 | Full end-to-end student journeys (Priya, Ravi, Karthik), crash survival, revision limits |
| [`test_selector.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_selector.py) | 14 | Mathematical formula validation, history-driven selection, Attempt 2 switching |
| [`test_store.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/tests/test_store.py) | 13 | Append-only SQLite verification, version sequencing, cross-connection read consistency |
| **Total** | **125** | **100% Pass Rate (0 Failures, 0 Regressions)** |

---

## Human Testing & Evaluation

All features in AdaptTutor were iteratively designed and validated through **real human student evaluations** and feedback collected via **standardized Google Forms**:

- **Roopa Varshni** (*Walkthrough 1*): Personalized explanations, student mastery context, 3-part analogy scaffold ([`walkthrough-1.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-1.md)).
- **Jeeva S** (*Walkthrough 2*): Mistake-specific failed retest feedback and misconception diagnosis ([`walkthrough-2.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-2.md)).
- **Sripramod Y** (*Walkthrough 3*): Clear learning state and next goal presentation cards ([`walkthrough-3.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-3.md)).
- **Vikram Dharshan** (*Stress Testing*): Adverse boundary conditions, retest pool exhaustion, guided practice, and 1-retry bounded loops ([`stress-test.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/stress-test.md)).

See the formal declaration in [`docs/USER_TESTING_DECLARATION.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/USER_TESTING_DECLARATION.md).
