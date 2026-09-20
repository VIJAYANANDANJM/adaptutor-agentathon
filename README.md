# AdaptTutor

**Agentic Adaptive Tutoring System for CS3301 Data Structures — Recursion Lab**

Team uniCode | B.E. CSE, College of Engineering Guindy, Anna University

---

## What It Does

AdaptTutor diagnoses individual student misconceptions in recursion and delivers
targeted remediation using adaptive explanation styles. When a student gets a
quiz question wrong, the system:

1. **Diagnoses** which concept they misunderstand (base case, recursive step,
   call stack, return propagation)
2. **Selects** the best explanation style (analogy or trace) based on what has
   historically worked for this student and concept
3. **Explains** the concept using the chosen style
4. **Retests** with a new question on the same concept
5. **Adapts** — if the retest fails and another style exists, it loops back
   and tries the other style
6. **Escalates** — if both styles fail, flags the instructor with specific
   context about what was tried and failed

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run environment diagnostics
python scripts/doctor.py

# 3. Run all tests (zero network, zero API keys)
python -m pytest

# 4. Start an interactive session
python run.py session student_123

# 5. List past runs
python run.py list

# 6. Replay a run's history
python run.py replay <run_id>
```

## Environment Setup

```bash
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY
python scripts/doctor.py    # verify connectivity
python run.py session student_123
```

## Architecture

```
adapt-tutor/
├── slice/              # Core Engine (spine from agentic-slice-kit)
│   ├── records.py      # RunState, Version, Question
│   ├── store.py        # Append-only SQLite persistence
│   ├── runner.py       # Deterministic state machine
│   ├── llm.py          # Single LLM choke point
│   ├── budget.py       # Token & attempt fences
│   ├── callback.py     # Human-in-the-loop suspension
│   └── config.py       # Settings from .env
│
├── remediation/        # Domain Layer (CS3301 Recursion)
│   ├── schema.py       # Pydantic schemas for all records
│   ├── questions.py    # Fixed 8-question quiz + retest bank
│   ├── provider.py     # Real LLM explanation provider
│   ├── flow.py         # State machine: QUIZ→DIAGNOSE→SELECT→EXPLAIN→RETEST→EVALUATE
│   ├── stub.py         # Test persona data (Priya, Ravi, Karthik)
│   └── prompts/        # Style-specific prompt templates
│
├── web/                # Instructor Panel
│   └── expert.py       # FastAPI web interface for instructor flags
│
├── tests/              # Comprehensive test suite
├── scripts/doctor.py   # Pre-flight diagnostics
└── run.py              # CLI entrypoint
```

### State Machine

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
```

### Key Design Decisions

- **Deterministic scoring**: All quiz/retest scoring, concept mapping, style
  selection, and escalation decisions are made by code, never the LLM
- **Append-only persistence**: SQLite with triggers preventing updates/deletes
  on the versions table — full audit trail
- **Adaptive selection**: Style chosen based on student-specific history, then
  population-level win rates, with deterministic tie-breaking
- **Budget fences**: Max 10 model calls per session, max 2 explanation attempts
  per concept — enforced in the database, not in variables

## Instructor Panel

```bash
# Start the instructor web interface
uvicorn web.expert:app --host 0.0.0.0 --port 8000
```

When a student is flagged, the instructor sees the student ID, concept,
styles tried, and can submit a custom hint that resumes the student's session.

## Testing

```bash
# All tests
python -m pytest

# Specific test suites
python -m pytest tests/test_store.py          # Persistence tests
python -m pytest tests/test_runner.py         # State machine tests
python -m pytest tests/test_budget.py         # Budget fence tests
python -m pytest tests/test_callback.py       # Instructor callback tests
python -m pytest tests/test_remediation.py    # Quiz scoring & style selection
python -m pytest tests/test_scenarios.py      # End-to-end Priya/Ravi/Karthik
```

## Test Personas

| Persona  | Scenario | Expected Outcome |
|----------|----------|------------------|
| Priya    | Fails Q5 (call_stack), passes retest with analogy | COMPLETE |
| Ravi     | Fails Q5+Q7, analogy fails on call_stack → backward loop → trace works | COMPLETE |
| Karthik  | Fails call_stack on both styles → instructor flag | AWAITING_EXPERT |
