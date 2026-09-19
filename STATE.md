# AdaptTutor Project State & Agent Handoff

**Current Phase:** Phase 6: Topic-Agnostic Dynamic Multi-Module Curriculum
**Current Build Status:** Green (all 101 tests passing)
**Last Updated:** 2026-09-19T17:05:00+05:30
**Active Git Branch:** `feat/topic-agnostic-curriculum`
**Last Completed Git Commit:** `6ddee1c` feat: display instructor guidance banner and transition feedback on session resumption
**Active Repository Remote:** `https://github.com/VIJAYANANDANJM/adaptutor-agentathon.git`

## 1. What Is Completed & Verified

- [x] Spine files from agentic-slice-kit (records, store, runner, llm, budget, callback, config)
- [x] Store extended with `all_versions_by_kind()` for population-level queries
- [x] Config extended with `llm_mode` for mock/real provider switching
- [x] Fixed 8-question quiz schema and data in `data/quiz.json` (2 per concept, 4 concepts)
- [x] Fixed retest question bank with variant questions in `data/retest_questions.json`
- [x] Dynamic multi-module curriculum loader in `remediation/curriculum.py`
- [x] Pre-packaged curriculum modules: `data/modules/python_recursion.json` and `data/modules/db_normalization.json`
- [x] AI Curriculum Generator (`remediation/curriculum_generator.py`) using OpenRouter and mock fallback
- [x] Pydantic schemas for all domain records (`remediation/schema.py`)
- [x] MockExplanationProvider with canned and dynamic domain explanations
- [x] RealLLMExplanationProvider calling `slice.llm.complete()` with OpenRouter (`openrouter/free`)
- [x] Exponential backoff retry and 120s timeout on OpenRouter completion
- [x] Remediation state machine (QUIZ→DIAGNOSE→SELECT→EXPLAIN→RETEST→EVALUATE)
- [x] Backward loop (failed retest → SELECT with alternate style)
- [x] Instructor escalation (both styles fail → AWAITING_EXPERT)
- [x] Instructor response handling & prominent guidance banner shown to student upon session resumption
- [x] Adaptive style selection with dynamic module styles ($0.7 \times \text{StudentRate} + 0.3 \times \text{CohortRate}$)
- [x] Persistent Learner Model (`remediation/learner.py` + `slice/store.py` SQLite learner tables)
- [x] Visible Adaptation UI Cards (`run.py` knowledge gap, retest evaluation, adaptation, and escalation cards)
- [x] Interactive Student Course Catalog CLI (`run.py session <student_id>` + `--module <id>` flag + resume vs new session)
- [x] Instructor Web Panel (`web/expert.py`) with Escalations, Student Roster (`/students`), and Curriculum Manager (`/curriculum`)
- [x] Comprehensive Verification Tests (`tests/test_curriculum.py`, `tests/test_learner.py`, `tests/test_selector.py`)
- [x] All 101 tests passing (`pytest -v`)

## 2. Completed Milestones

- **Multi-Module Curriculum Engine**: Seamless support for any subject (Python Recursion, Relational Normalization, Operating Systems, etc.) in `data/modules/`.
- **AI Curriculum Generator**: OpenRouter automatically creates diagnostic quizzes, retest banks, and domain explanation styles from an instructor topic prompt.
- **Interactive Student Catalog**: In CLI, students view mastery across subjects, receive automated recommendations, and choose modules.
- **Persistent Learner Model**: Explicit concept-wise mastery % (0-100%), weak/strong concept tags, and intervention history tracking across sessions in SQLite.
- **Evidence-Based Adaptive Selector**: Deterministic mathematical style ranker with zero LLM grading/selection.
- **Visible Adaptation UI**: Structured terminal cards rendering Knowledge Gap, Current Mastery, Previous Interventions, Selected Style, Reason, and Post-Retest Mastery Change ($X\% \to Y\%$).
- **Instructor Dashboard**: Web UI view for student mastery analytics, style efficacy, active escalations, and curriculum creator at `http://127.0.0.1:8000`.

## 3. Current Test Health Summary

- Total Tests: 101 | Passed: 101 | Failed: 0
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
  - `test_curriculum.py` (6 tests): Module listing, dynamic module loading, multi-module scoring, AI mock generation, and end-to-end multi-module remediation

## 4. Current Environment & Configuration

- `LLM_MODE=real` (OpenRouter integration via `.env`)
- `SLICE_MODEL=openrouter/free`
- Instructor Web Server: `python -m uvicorn web.expert:app --host 127.0.0.1 --port 8000 --reload`
- Active SQLite Database: `run.db` (append-only events + runs + questions + learner model)
