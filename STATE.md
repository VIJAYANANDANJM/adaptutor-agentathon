# AdaptTutor Project State & Agent Handoff

**Current Phase:** Phase 4: V1 Complete
**Current Build Status:** Green (all 55 tests passing)
**Last Updated:** 2026-09-19T14:01:00+05:30
**Last Completed Git Commit:** `22b0d5a` fix: resolve retest prompt handling in interactive CLI

## 1. What Is Completed & Verified

- [x] Spine files from agentic-slice-kit (records, store, runner, llm, budget, callback, config)
- [x] Store extended with `all_versions_by_kind()` for population-level queries
- [x] Config extended with `llm_mode` for mock/real provider switching
- [x] Fixed 8-question quiz schema and data in `data/quiz.json` (2 per concept, 4 concepts)
- [x] Fixed retest question bank with variant questions in `data/retest_questions.json`
- [x] `remediation/questions.py` refactored to dynamically load and validate curriculum JSON files
- [x] Pydantic schemas for all domain records
- [x] MockExplanationProvider with canned style-specific responses
- [x] RealLLMExplanationProvider calling slice.llm.complete()
- [x] Remediation state machine (QUIZ→DIAGNOSE→SELECT→EXPLAIN→RETEST→EVALUATE)
- [x] Backward loop (failed retest → SELECT with alternate style)
- [x] Instructor escalation (both styles fail → AWAITING_EXPERT)
- [x] Instructor response handling (resume → RESOLVED or timeout → CLOSED_UNRESOLVED)
- [x] Adaptive style selection (student-specific → population-level → default)
- [x] Test persona stubs (Priya, Ravi, Karthik)
- [x] Prompt templates for analogy and trace styles
- [x] Instructor web panel (FastAPI)
- [x] CLI entrypoint (session, replay, list, doctor)
- [x] Doctor script passes clean
- [x] PRE-EVENT-ASSETS.md declared
- [x] AgentSpec-uniCode.md present
- [x] README.md complete
- [x] STATE.md maintained
- [x] All 55 tests passing

## 2. Active Work In Progress

- [ ] None — V1 is complete

## 3. Next Immediate Steps (Handoff Instructions)

1. Run `git init && git add -A && git commit -m "V1: AdaptTutor complete"` to create first commit
2. To verify: `python -m pytest -v` (55 tests, all pass)
3. To verify doctor: `python scripts/doctor.py` (all clear)
4. To run interactive session: `python run.py session student_123`
5. To start instructor panel: `uvicorn web.expert:app --host 0.0.0.0 --port 8000`

## 4. Test Health Summary

- Total Tests: 55 | Passed: 55 | Failed: 0
- Last command run: `python -m pytest -v`
- Test coverage:
  - `test_store.py` (13 tests): Persistence, append-only triggers, cross-connection
  - `test_runner.py` (4 tests): State machine, max steps, suspension
  - `test_budget.py` (8 tests): Token fences, attempts, restart survival
  - `test_callback.py` (7 tests): Suspension, resume, write-once, timeout
  - `test_remediation.py` (15 tests): Quiz scoring, style selection, mock provider, question bank
  - `test_scenarios.py` (8 tests): Priya, Ravi, Karthik E2E + revision limits + process interruption

## 5. Architectural Notes & Decisions

- State machine maps domain steps to RunState: DRAFTING=EXPLAIN, GATING=SELECT, PROBING=RETEST
- QUIZ→DIAGNOSE runs inline via `start_session()` because quiz submission is provided upfront
- Retest suspension uses AWAITING_EXPERT with `awaiting_retest` marker to differentiate from instructor suspension
- Instructor response detection uses version sequence numbers to determine most recent action
- Four deliberate V1 weaknesses are present without code annotations
- `retrieve.py` (vector/RAG) deliberately excluded — not needed for this domain
