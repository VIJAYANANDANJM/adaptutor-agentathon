# Walkthrough 1

*Tester:* Roopa Varshni  
*Date:* 19 September 2026  
*Duration:* 20 minutes

## What did you think it was going to do?

Roopa expected the agent to help a student understand a concept by
explaining the answer and addressing the student's specific
misunderstanding.

## Where did you get stuck?

Roopa was able to complete the intended flow without major difficulty.
The main observation was that, although the explanations were clear,
they could be more personalized to the individual student.

## What would you have wanted it to do instead?

> "The explanations were clear and easy to understand, but they could
> be more personal to each student. It would be better if the agent
> understood the student's level and used examples or analogies that
> the student could relate to."

## Iteration

Based on this feedback, we changed the context provided to the LLM so
that the agent has more information about the student's question,
misconception, learning objective, and learner profile.

### Changes made

| Dimension | Before | Now on main |
|---|---|---|
| *Question Options* | Only raw letters (b, a) | Full options block with text for A, B, C, D |
| *Misconception Targeting* | LLM had to guess what b meant | Explicitly tagged: [A] 4 frames ← STUDENT'S WRONG CHOICE |
| *Concept Framing* | Raw snake_case ID (call_stack) | Formatted concept name + Learning Objective |
| *Learner Profile* | Completely blind | Injected: Mastery: 25%, Attempt: 2 of 2, Prior failed styles: Trace |
| *Analogy Rules* | Generic rules | 3-Part Scaffold: Physical Anchor → Misconception Hook → Resolution |

These changes allow the agent to generate explanations that are more
specific to the student's current knowledge, misconception, and
learning history, rather than providing the same generic explanation
to every student.

## Result

The updated agent now receives explicit learner and misconception
context and has structured instructions for choosing relevant
analogies and framing explanations.

*Commit:* `55c4908` — Improve personalized explanations based on walkthrough 1