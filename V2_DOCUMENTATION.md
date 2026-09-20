# AdaptTutor — Complete Implementation & Architecture Documentation

**Institution:** College of Engineering Guindy — Team uniCode  
**Event:** Agentathon 2026  
**Current Status:** Production Ready (**125 / 125 Tests Passing**)  
**Judge Entrypoint:** [`RUN.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/RUN.md) (`python run.py demo`)  

---

## 1. Executive Summary

AdaptTutor is an **evidence-based, intelligent remediation platform** for computer science education. It diagnoses student knowledge gaps and delivers targeted, adaptive interventions. Traditional conversational AI tutors frequently suffer from two critical flaws:
1. **Unbounded conversations and scoring hallucinations** when grading quizzes or evaluating code.
2. **One-size-fits-all pedagogy** that delivers identical generic explanations to students with vastly different cognitive models.

AdaptTutor solves these problems by strictly enforcing the **Agentic Slice principle**:
- **Deterministic Python Engine**: Evaluates diagnostic quizzes, selects instructional styles using a multi-armed bandit algorithm, tracks EMA concept mastery in SQLite, bounds retry loops, handles question exhaustion, and manages instructor escalations.
- **Isolated LLM Layer**: Leverages the Large Language Model via OpenRouter (`slice/llm.py`) strictly as a bounded text generation engine for high-quality pedagogical explanations, mistake diagnoses, and curriculum synthesis.

---

## 2. Complete Workflow Diagram

```text
               ┌────────────────────────┐
               │    DIAGNOSTIC QUIZ     │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │   DIAGNOSE GAPS        │
               │  (Set-difference math) │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │ 🎯 YOUR LEARNING STATE │
               │ (Mastery % + Concept)  │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │  SELECT & EXPLAIN      │
               │ (Analogy vs. Trace)    │
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
  Mastery += 45% (cap 95%)        Mastery -= 15% (floor 10%)
  ✓ CONCEPT IMPROVED                      │
  Next Gap / Complete                     ▼
                             ┌────────────────────────┐
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
  (0.7*Student + 0.3*Cohort)                                           │
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

## 3. Core Subsystems & Components

### 3.1 Persistent Learner Model ([`remediation/learner.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/learner.py))
- **SQLite Tables**:
  - `learner_profiles`: Stores `(student_id, concept, mastery, updated_at)`.
  - `intervention_history`: Stores `(id, student_id, concept, style, attempt, passed, created_at)`.
- **Mastery Math ($\alpha = 0.3$ EMA)**:
  - Initial Diagnostic Quiz error initializes mastery to 25% ($0.25$).
  - Correct diagnostic answer initializes mastery to 85% ($0.85$).
  - Passing a retest awards $+45\%$ ($+0.45$), capped at 95% ($0.95$).
  - Failing a retest penalizes $-15\%$ ($-0.15$), floored at 10% ($0.10$).
- **Classification**: Concepts with $\ge 75\%$ mastery are classified as `STRONG`; concepts $< 60\%$ are classified as `WEAK`.

### 3.2 Evidence-Based Adaptive Style Selector ([`remediation/selector.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/selector.py))
- **Mathematical Formula**:
  $$\text{Score}(\text{style}) = 0.7 \times \text{StudentWinRate}(\text{style}) + 0.3 \times \text{CohortWinRate}(\text{style})$$
- **Attempt 2 Adaptation Invariant**: When Attempt 1 fails, Attempt 2 is strictly constrained to switch to an untried pedagogical style (e.g., Analogy $\to$ Trace).

### 3.3 Context-Enriched Pedagogical Explanation Provider ([`remediation/provider.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/provider.py))
- **Prompt Injection**: Injects the full question options dictionary, student mastery %, attempt history, and explicit distractor tags:
  ```text
  [A] 4 frames  <-- [STUDENT'S WRONG CHOICE]
  [B] 5 frames  <-- [CORRECT ANSWER]
  ```
- **3-Part Analogy Scaffold**: Structured prompt rules: Physical Anchor $\to$ Misconception Hook $\to$ Solution Emergence.

### 3.4 Mistake-Specific Failed Retest Diagnosis ([`remediation/feedback.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/feedback.py))
- Evaluates the misconception behind the learner's chosen wrong option.
- Renders the terminal card `🔍 RETEST FEEDBACK — MISTAKE DIAGNOSIS` with `Why your answer was wrong` (<50 words) and `What to remember` (<25 words).
- Zero-crash deterministic fallback if LLM times out or is unreachable.

### 3.5 Pedagogical Goals & Learning State Cards ([`remediation/goals.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/goals.py))
- `print_learning_state_card(...)`: Compact card displayed before each explanation showing concept, mastery progress bar, previous approach failure tag (`❌`), adaptation reason, and concrete learning objective.
- `print_concept_improved_card(...)`: Displayed upon passing a retest showing `old% ➔ new%`, positive delta ($+45\%$), confirmation of goal achieved, and clear next step pointer.

### 3.6 Retest Pool Exhaustion, Guided Practice & Fresh Retests ([`remediation/practice.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/practice.py))
- **Question Tracking**: Logs attempted question texts in SQLite; guarantees questions never repeat while unused questions remain.
- **Exhaustion Detection**: When curated retest questions run out, triggers `⚠️ RETEST POOL EXHAUSTED` card and switches to `GUIDED PRACTICE`.
- **Guided Practice**: Delivers concept-specific, 2–4 progressive reasoning steps with immediate feedback.
- **1-Retry Bound**: Enforces a strict limit of at most 1 retry per step with targeted hints, preventing infinite loops.
- **Fresh Retests**: Upon completing guided practice (`✓ GUIDED PRACTICE COMPLETE`), presents an independent, previously unseen validation question.
- **Resumption**: Interrupted sessions resume at the exact incomplete step from SQLite event logs.

### 3.7 Topic-Agnostic Curriculum Engine & AI Generator ([`remediation/curriculum.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/remediation/curriculum.py))
- Modular course packages in `data/modules/`:
  - `python_recursion.json`
  - `db_normalization.json`
  - `operating_systems_virtual.json`
  - `iot_mqtt.json`
- AI Curriculum Generator (`remediation/curriculum_generator.py`) allowing instant creation of new 4-concept courses from a simple topic prompt.

### 3.8 Human-in-the-Loop Web Portal ([`web/expert.py`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/web/expert.py))
- Real-time FastAPI web dashboard at `http://127.0.0.1:8000`.
- Features: Pending escalation queue, full student mastery roster (`/students`), style efficacy analytics, and curriculum creator.

---

## 4. Verification & Automated Test Suite

The system is validated by **125 automated unit and end-to-end scenario tests** with a **100% pass rate**:

```text
============================= test session starts =============================
collected 125 items

tests/test_budget.py ........                                            [  6%]
tests/test_callback.py .......                                           [ 12%]
tests/test_curriculum.py ......                                          [ 16%]
tests/test_feedback.py ......                                            [ 21%]
tests/test_goals.py ........                                             [ 28%]
tests/test_learner.py ........................                           [ 47%]
tests/test_practice.py .........                                         [ 54%]
tests/test_remediation.py ................                               [ 67%]
tests/test_runner.py ....                                                [ 70%]
tests/test_scenarios.py ........                                         [ 76%]
tests/test_selector.py ................                                  [ 89%]
tests/test_store.py .............                                        [100%]

============================ 125 passed in 18.42s =============================
```

---

## 5. Judge Execution & Demo Commands

To run the live demo, refer to [`RUN.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/RUN.md):

```bash
# Set key (or load directly from .env)
export OPENROUTER_API_KEY="your-openrouter-api-key"

# Run the 3-persona demo showcasing all adaptive capabilities
python run.py demo
```
