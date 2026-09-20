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
- [x] Config configured with `LLM_MODE=real`
- [x] Fixed 8-question quiz schema and data in `data/quiz.json` (2 per concept, 4 concepts)
- [x] Fixed retest question bank with variant questions in `data/retest_questions.json`
- [x] Dynamic multi-module curriculum loader in `remediation/curriculum.py`
- [x] Pre-packaged curriculum modules: `data/modules/python_recursion.json` and `data/modules/db_normalization.json`
- [x] AI Curriculum Generator (`remediation/curriculum_generator.py`) using OpenRouter and mock fallback
- [x] Pydantic schemas for all domain records (`remediation/schema.py`)
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
- **Self-Contained Module Prompts**: Each curriculum JSON encapsulates its own `style_descriptions`. The AI generator (or instructor) embeds pedagogical style rules directly inside the `.json`. The runtime engine (`remediation/provider.py`) dynamically constructs the full pedagogical prompt with guardrails, rendering `remediation/prompts/*.md` as an optional legacy fallback. Zero manual prompt file editing is required for new courses.
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
  - `test_remediation.py` (15 tests): Quiz scoring, style selection, real LLM provider, question bank
  - `test_scenarios.py` (8 tests): Priya, Ravi, Karthik E2E + revision limits + process interruption
  - `test_learner.py` (22 tests): Mastery init, retest updates, instructor updates, classification, style win-rate, persistence
  - `test_selector.py` (14 tests): Formula verification, different histories -> different selections, attempt 2 never repeats, fallback behavior, demo personas, reasons
  - `test_curriculum.py` (6 tests): Module listing, dynamic module loading, multi-module scoring, AI mock generation, and end-to-end multi-module remediation

## 4. Current Environment & Configuration

- `LLM_MODE=real` (OpenRouter integration via `.env`)
- `SLICE_MODEL=openrouter/free`
- Instructor Web Server: `python -m uvicorn web.expert:app --host 127.0.0.1 --port 8000 --reload`
- Active SQLite Database: `run.db` (append-only events + runs + questions + learner model)

## 5. Architectural Decision: Dynamic Prompts vs. `remediation/prompts/` Directory

### Context
In V1, explanation prompts were static markdown files on disk (`remediation/prompts/analogy.md` and `remediation/prompts/trace.md`) with hardcoded references to recursion.

### Upgraded Architecture in V2 / Multi-Module
1. **JSON as Single Source of Truth**:
   - Each curriculum package in `data/modules/<module_id>.json` contains a `style_descriptions` mapping:
     ```json
     "style_descriptions": {
       "worked_example": "Step-by-step table decomposition showing functional dependencies...",
       "analogy": "Real-world organizational analogies such as filing systems..."
     }
     ```
2. **Authoring Automation**:
   - When an instructor uses the AI Curriculum Generator (`remediation/curriculum_generator.py` or `/curriculum` web UI), OpenRouter automatically authors the domain-tailored `style_descriptions` directly inside the `.json`.
   - When an instructor creates a module manually, they provide 1–2 descriptive sentences in the JSON.
3. **Runtime Dynamic Prompt Construction**:
   - `remediation/provider.py` receives the active module's `title`, concept display name, and `style_instruction` dynamically.
   - It wraps these into a rigorous system prompt with universal pedagogical rules (diagnosing specific error, word count under 180 words, non-condescending tone, conceptual clarity without spoiling retest).
4. **Role of `remediation/prompts/`**:
   - The `.md` files in `remediation/prompts/` are preserved **strictly as a legacy fallback** for the base recursion module.
   - **No developer or instructor ever needs to create, edit, or maintain `.md` prompt files when introducing new subjects.** Every domain (from Database Normalization to OS Paging to Physics) is completely self-contained in its JSON package.

