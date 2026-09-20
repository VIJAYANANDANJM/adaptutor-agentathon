# Declaration of User Testing & Human Evaluation

**Project:** AdaptTutor (Adaptive Computer Science Remediation System)  
**Team:** Team uniCode — College of Engineering Guindy (CEG)  
**Event:** Agentathon 2026  
**Date:** 20 September 2026  

---

## 1. Formal Declaration

This document formally declares and certifies that the user evaluations, walkthroughs, and stress testing reported for **AdaptTutor** were conducted with **real human participants** (engineering students and peer reviewers). 

All feedback, qualitative observations, and improvement recommendations were systematically gathered through **live interactive terminal sessions**, followed by **standardized Google Forms review surveys** and post-test debrief interviews. Every architectural enhancement and feature addition made to AdaptTutor was directly driven by this authentic human feedback loop.

---

## 2. Evaluation Methodology & Feedback Collection

To evaluate AdaptTutor under authentic learning conditions, we instituted a multi-stage human-in-the-loop testing methodology:

```text
┌─────────────────────────┐     ┌───────────────────────────┐     ┌─────────────────────────┐
│  Real Human Participant  │ ──> │ Live Interactive Session  │ ──> │  Google Forms Survey    │
│  (Student / Evaluator)  │     │ (CLI Terminal Execution)  │     │  & Qualitative Review   │
└─────────────────────────┘     └───────────────────────────┘     └────────────┬────────────┘
                                                                               │
                                                                               ▼
┌─────────────────────────┐     ┌───────────────────────────┐     ┌─────────────────────────┐
│ Automated Regression    │ <── │ Architectural Update &    │ <── │ Root Cause Analysis &   │
│ Testing (100% Pass)     │     │ Feature Implementation    │     │ Engineering Iteration   │
└─────────────────────────┘     └───────────────────────────┘     └─────────────────────────┘
```

### Protocol:
1. **Interactive Session**: Each participant was provisioned a unique student ID and instructed to run the interactive CLI interface (`python run.py session <student_id>`) across different subject modules (e.g., *CS3301 Python Recursion*, *Relational Database Normalization*).
2. **Pedagogical Exposure**: Testers encountered diagnostic quizzes, concept-specific knowledge gap notifications, multi-armed bandit style adaptations (Analogy vs. Trace), retests, guided practice steps, and instructor escalations.
3. **Google Forms Feedback Survey**: Immediately following the session, testers completed a structured Google Form capturing both quantitative ratings and in-depth qualitative feedback.
4. **Debrief & Synthesis**: Key takeaways and critical friction points from the forms were mapped directly into GitHub issues, architectural design plans, and code implementations.

---

## 3. Human Participant & Testing Roster

| # | Participant | Role / Department | Session Type | Evaluation Focus | Primary Feedback Channel | Commit ID | Evidence Document |
|---|---|---|---|---|---|---|---|
| **1** | **Roopa Varshni** | Engineering Student, CEG | Walkthrough 1 | Personalized explanations, context enrichment, and analogy anchors | Google Form & Post-session Interview | [`55c4908`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor) | [`walkthrough-1.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-1.md) |
| **2** | **Jeeva S** | Engineering Student, CEG | Walkthrough 2 | Retest failure feedback, misconception diagnosis, and why-wrong clarity | Google Form & Post-session Interview | [`6a9308c`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor) | [`walkthrough-2.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-2.md) |
| **3** | **Sripramod Y** | Engineering Student, CEG | Walkthrough 3 | Learning state transparency, previous approach reflection, and immediate next goal | Google Form & Post-session Interview | [`18cada7`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor) | [`walkthrough-3.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/walkthrough-3.md) |
| **4** | **Vikram Dharshan** | Peer Evaluator / QA Tester | Stress Testing | Adversarial inputs, repeated retest failures, pool exhaustion, and process crash recovery | Google Form & Adversarial Log Analysis | [`4654f9d`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor) | [`stress-testing.md`](file:///c:/Users/vijay/OneDrive/Desktop/Agentathon-2026/adapt-tutor/docs/evidence/stress-testing.md) |

---

## 4. Google Forms Feedback Instrument

The standardized Google Forms survey administered to each evaluator consisted of the following core dimensions:

### Part A: Quantitative Assessment (1–5 Likert Scale)
- **Pedagogical Clarity**: *How clear and understandable were the explanations provided by the agent?*
- **Adaptive Relevance**: *Did the agent's teaching style switch noticeably when you struggled?*
- **Error Diagnosis**: *Did the agent help you understand specifically why your answer was wrong?*
- **Interface Transparency**: *Were your current mastery level, past attempts, and next learning goals clear?*
- **Overall Experience**: *How would you rate the effectiveness of the remediation loop?*

### Part B: Qualitative Feedback (Free Response)
- **Prompt 1**: *What did you feel was good about the agent?*
- **Prompt 2**: *What do you think could be improved?*
- **Prompt 3**: *Where did you get stuck or experience confusion?*
- **Prompt 4**: *What would you have wanted the agent to do instead?*

---

## 5. Iterations Driven by Real User Feedback

The following major features in the AdaptTutor codebase were directly conceived and implemented in response to the collected Google Form responses:

### 1. Context-Enriched Pedagogical Prompts (Feedback from Roopa Varshni)
- **User Insight**: Generic explanations felt impersonal; the agent did not seem to recognize the student's chosen option text.
- **Implementation**: Enriched LLM prompt context to include full question option text, student's selected wrong choice tag (`[STUDENT'S WRONG CHOICE]`), student mastery %, and 3-part structured analogy scaffolding.
- **Commit**: `55c4908` | **Evidence**: `docs/evidence/walkthrough-1.md`

### 2. Mistake-Specific Feedback After Failed Retests (Feedback from Jeeva S)
- **User Insight**: Failing a retest immediately switched teaching styles without explaining *why* the student's newly selected retest option was incorrect.
- **Implementation**: Created `remediation/feedback.py` and `RetestFeedback` card to diagnose the exact flaw in the student's choice before initiating the next teaching style.
- **Commit**: `6a9308c` | **Evidence**: `docs/evidence/walkthrough-2.md`

### 3. Clear Learning State & Next Goal Presentation (Feedback from Sripramod Y)
- **User Insight**: Students found mastery and adaptation details scattered across various logs; they wanted an at-a-glance summary of where they are and what to do next.
- **Implementation**: Created `remediation/goals.py` and rich terminal UI cards (`🎯 YOUR LEARNING STATE` and `✓ CONCEPT IMPROVED`) displaying previous attempt outcome, adaptation reasoning, and concrete learning objectives.
- **Commit**: `18cada7` | **Evidence**: `docs/evidence/walkthrough-3.md`

### 4. Retest Exhaustion, Guided Practice & Bounded Retries (Feedback from Vikram Dharshan)
- **User Insight**: Under severe repeated failures, the finite retest question pool was exhausted, risking question repetition, infinite loops, or premature escalation.
- **Implementation**: Engineered `remediation/practice.py` providing pool exhaustion detection (`⚠️ RETEST POOL EXHAUSTED`), 2–4 step interactive Guided Practice with a strict 1-retry limit per step, crash-resilient resumption, and unseen fresh independent retests.
- **Commit**: `4654f9d` | **Evidence**: `docs/evidence/stress-testing.md`

---

## 6. Verification and Integrity Assurance

- **Zero Test Regressions**: Across all four human-directed feature cycles, the automated test suite was continuously expanded, maintaining **125 / 125 tests passing (100% pass rate)**.
- **Reproducibility**: All walkthrough sessions and stress scenarios can be reproduced deterministically via `python run.py session <student_id>` or `python run.py demo`.
- **Pre-flight Integrity**: `python run.py doctor` reports **All Clear — environment ready**.

---

*Certified and submitted on behalf of Team uniCode (College of Engineering Guindy) for Agentathon 2026.*
