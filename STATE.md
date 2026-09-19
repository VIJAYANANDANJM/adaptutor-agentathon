# AdaptTutor Project State & Agent Handoff

**Current Phase:** Phase 5: Production Hardening & V1.1 Readiness
**Current Build Status:** Green (all 55 tests passing)
**Last Updated:** 2026-09-19T15:20:00+05:30
**Last Completed Git Commit:** `6ddee1c` feat: display instructor guidance banner and transition feedback on session resumption
**Active Repository Remote:** `https://github.com/VIJAYANANDANJM/adaptutor-agentathon.git`

## 1. What Is Completed & Verified

- [x] Spine files from agentic-slice-kit (records, store, runner, llm, budget, callback, config)
- [x] Store extended with `all_versions_by_kind()` for population-level queries
- [x] Config extended with `llm_mode` for mock/real provider switching
- [x] Fixed 8-question quiz schema and data in `data/quiz.json` (2 per concept, 4 concepts)
- [x] Fixed retest question bank with variant questions in `data/retest_questions.json`
- [x] `remediation/questions.py` refactored to dynamically load and validate curriculum JSON files
- [x] Pydantic schemas for all domain records (`remediation/schema.py`)
- [x] MockExplanationProvider with canned style-specific responses
- [x] RealLLMExplanationProvider calling `slice.llm.complete()` with OpenRouter (`openrouter/free`)
- [x] Exponential backoff retry and 120s timeout on OpenRouter completion
- [x] Remediation state machine (QUIZ→DIAGNOSE→SELECT→EXPLAIN→RETEST→EVALUATE)
- [x] Backward loop (failed retest → SELECT with alternate style)
- [x] Instructor escalation (both styles fail → AWAITING_EXPERT)
- [x] Instructor response handling & prominent guidance banner shown to student upon session resumption
- [x] Adaptive style selection (student-specific → population-level → default)
- [x] Test persona stubs (Priya, Ravi, Karthik)
- [x] Prompt templates for analogy and trace styles
- [x] Instructor web panel (`web/expert.py` on port 8000) with robust form handling independent of python-multipart
- [x] CLI entrypoint (`run.py`: session, replay, list, doctor)
- [x] Doctor script passes clean (`scripts/doctor.py`)
- [x] PRE-EVENT-ASSETS.md declared & AgentSpec-uniCode.md aligned
- [x] Persistent Learner Model (`remediation/learner.py` + `slice/store.py` SQLite learner tables)
- [x] Evidence-Based Adaptive Selector (`remediation/selector.py` with weighted student/cohort formula)
- [x] Visible Adaptation UI Cards (`run.py` knowledge gap, retest evaluation, adaptation, and escalation cards)
- [x] Enriched Instructor Dashboard (`web/expert.py` with `/students` roster & enriched escalation queue)
- [x] Deterministic Demo Personas (`remediation/stub.py` & `scripts/seed_demo.py` for 3 personas)
- [x] Comprehensive Verification Tests (`tests/test_learner.py` & `tests/test_selector.py`)
- [x] All 95 tests passing (`pytest`)

## 2. Completed V2 Upgrades

- **Persistent Learner Model**: Explicit concept-wise mastery % (0-100%), weak/strong concept tags, and intervention history tracking across sessions in SQLite.
- **Evidence-Based Adaptive Selector**: Deterministic mathematical style ranker ($0.7 \times \text{StudentRate} + 0.3 \times \text{CohortRate}$) with zero LLM grading/selection.
- **Visible Adaptation UI**: Structured terminal cards rendering Knowledge Gap, Current Mastery, Previous Interventions, Selected Style, Reason, and Post-Retest Mastery Change ($X\% \to Y\%$).
- **Enriched Instructor Dashboard**: Web UI view for student mastery analytics, style efficacy, and escalation details with student roster.
- **Deterministic Demo Personas**: Pre-seeded students (Ananya: Analogy affinity, Bharat: Trace affinity, Karthik: Escalation candidate) runnable via `python run.py demo`.

## 3. Current Test Health Summary

- Total Tests: 95 | Passed: 95 | Failed: 0
- Last command run: `python -m pytest -v`
- Test coverage:
  - `test_store.py` (13 tests): Persistence, append-only triggers, cross-connection
  - `test_runner.py` (4 tests): State machine, max steps, suspension
  - `test_budget.py` (8 tests): Token fences, attempts, restart survival
  - `test_callback.py` (7 tests): Suspension, resume, write-once, timeout
  - `test_remediation.py` (15 tests): Quiz scoring, style selection, mock provider, question bank
  - `test_scenarios.py` (8 tests): Priya, Ravi, Karthik E2E + revision limits + process interruption
  - `test_learner.py` (22 tests): Mastery init, retest updates, instructor updates, classification, style win-rate, persistence
  - `test_selector.py` (14 tests): Formula verification, different histories -> different selections, attempt 2 never repeats, fallback behavior, demo personas, reasons

## 4. Current Environment & Configuration

- `LLM_MODE=real` (OpenRouter integration via `.env`)
- `SLICE_MODEL=openrouter/free`
- Instructor Web Server: `python -m uvicorn web.expert:app --host 127.0.0.1 --port 8000`
- Active SQLite Database: `run.db` (append-only events + runs + questions)
