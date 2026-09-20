"""
remediation/practice.py — Retest Pool Exhaustion, Guided Practice, and Fresh Retest Engine.

Provides:
1. Question pool tracking to prevent repeating questions and detect pool exhaustion.
2. Progressive multi-step Guided Practice reasoning chains (topic-agnostic, with LLM and offline fallbacks).
3. Fresh independent retest question generation and delivery.
4. Persistent session tracking for guided practice progress and resume capabilities.
"""
from __future__ import annotations

import json
from typing import Any
from pydantic import BaseModel, Field

from slice.config import Settings
from slice.store import Store
from remediation.curriculum import CurriculumModule, get_module
from remediation.questions import RetestQuestion
from remediation.schema import GuidedStep, GuidedPracticeRecord


# ── Question Pool Tracking & Exhaustion Detection ─────────────────────────────

def get_attempted_question_texts(store: Store, run_id: str, concept: str) -> set[str]:
    """Retrieve all retest question texts already attempted for this concept in the run."""
    attempted = set()

    # From retest_result history
    for entry in store.history(run_id, "retest_result"):
        payload = entry.payload
        if payload.get("concept") == concept:
            txt = payload.get("question_text")
            if txt:
                attempted.add(txt.strip())

    # From retest_feedback history (always has question_text)
    for entry in store.history(run_id, "retest_feedback"):
        payload = entry.payload
        if payload.get("concept") == concept:
            txt = payload.get("question_text")
            if txt:
                attempted.add(txt.strip())

    return attempted


def get_curated_retest_pool(mod: CurriculumModule, concept: str) -> list[RetestQuestion]:
    """Get all curated retest questions defined in the module for a concept."""
    pool: list[RetestQuestion] = []
    q1 = mod.retest_attempt_1.get(concept)
    if q1:
        pool.append(q1)
    q2 = mod.retest_attempt_2.get(concept)
    if q2:
        pool.append(q2)
    return pool


def get_next_unused_retest_question(
    mod: CurriculumModule,
    concept: str,
    attempted_texts: set[str],
) -> RetestQuestion | None:
    """Return the next unused curated question, or None if all curated questions have been used."""
    pool = get_curated_retest_pool(mod, concept)
    for q in pool:
        if q.text.strip() not in attempted_texts:
            return q
    return None


def is_retest_pool_exhausted(
    mod: CurriculumModule,
    concept: str,
    attempted_texts: set[str],
) -> bool:
    """Return True if all curated retest questions for this concept have already been attempted."""
    return get_next_unused_retest_question(mod, concept, attempted_texts) is None


# ── Guided Practice Curated Reasoning Steps ───────────────────────────────────

CURATED_GUIDED_PRACTICE: dict[str, list[dict[str, Any]]] = {
    # ── Python Recursion ──────────────────────────────────────────────────────
    "call_stack": [
        {
            "step_number": 1,
            "total_steps": 3,
            "context": "factorial(3) calls factorial(2).",
            "prompt": "Which function call is currently active, and which is waiting?",
            "options": {
                "a": "factorial(3) is active, factorial(2) is waiting",
                "b": "factorial(2) is active, factorial(3) is waiting",
                "c": "Both are active and running at the exact same time",
            },
            "correct": "b",
            "explanation": "factorial(2) is the newly invoked callee executing at the top of the stack; factorial(3) pauses waiting for its return value.",
            "hint": "The most recently called function is active at the top of the call stack.",
        },
        {
            "step_number": 2,
            "total_steps": 3,
            "context": "Now factorial(2) calls factorial(1), and factorial(1) hits the base case n == 1.",
            "prompt": "Which stack frame will finish and be popped off the call stack first?",
            "options": {
                "a": "factorial(3)",
                "b": "factorial(2)",
                "c": "factorial(1)",
            },
            "correct": "c",
            "explanation": "The call stack operates in Last-In, First-Out (LIFO) order. factorial(1) hit the base case, so its frame pops first.",
            "hint": "In LIFO (stack order), the newest frame is popped first.",
        },
        {
            "step_number": 3,
            "total_steps": 3,
            "context": "factorial(1) returns 1 to factorial(2). factorial(2) computes 2 * 1 = 2.",
            "prompt": "When does factorial(3) resume and complete its computation?",
            "options": {
                "a": "Only after factorial(2) completes and returns 2 to factorial(3)",
                "b": "Immediately, without waiting for factorial(2) to return",
                "c": "It never resumes because recursive calls overwrite caller frames",
            },
            "correct": "a",
            "explanation": "Caller frames remain preserved on the call stack until their invoked sub-call returns a value back up the stack.",
            "hint": "The caller resumes precisely where it made the recursive call once the callee returns.",
        },
    ],
    "base_case": [
        {
            "step_number": 1,
            "total_steps": 3,
            "context": "Consider: def countdown(n): if n == 0: return; print(n); countdown(n-1)",
            "prompt": "Which line represents the base case?",
            "options": {
                "a": "print(n)",
                "b": "if n == 0: return",
                "c": "countdown(n-1)",
            },
            "correct": "b",
            "explanation": "'if n == 0: return' stops recursion by returning without calling countdown again.",
            "hint": "The base case is the conditional branch that does NOT call the function recursively.",
        },
        {
            "step_number": 2,
            "total_steps": 3,
            "context": "countdown(2) is called. It prints 2 and calls countdown(1).",
            "prompt": "What ensures this function will actually reach the base case?",
            "options": {
                "a": "The argument decreases toward 0 with each call (n-1)",
                "b": "Python automatically terminates recursive functions after 5 steps",
                "c": "The print statement reduces n",
            },
            "correct": "a",
            "explanation": "Each recursive call passes n-1, converging steadily toward the base case n == 0.",
            "hint": "Steady progress toward the termination condition is required to avoid infinite loops.",
        },
        {
            "step_number": 3,
            "total_steps": 3,
            "context": "Suppose the base case condition 'if n == 0:' was omitted entirely.",
            "prompt": "What would happen when running countdown(2)?",
            "options": {
                "a": "It would stop after printing 2",
                "b": "It would run through negative numbers until a RecursionError occurs",
                "c": "It would return 0 safely",
            },
            "correct": "b",
            "explanation": "Without a base case, calls continue indefinitely until the call stack limit is reached, raising a RecursionError.",
            "hint": "Without a stop condition, stack frames accumulate indefinitely.",
        },
    ],
    "recursive_step": [
        {
            "step_number": 1,
            "total_steps": 3,
            "context": "We want to compute sum_list([3, 1, 4]) recursively.",
            "prompt": "How do we break this problem into a head element and a smaller recursive sub-problem?",
            "options": {
                "a": "3 + sum_list([1, 4])",
                "b": "sum_list([3, 1]) + sum_list([4])",
                "c": "sum_list([3, 1, 4]) + 1",
            },
            "correct": "a",
            "explanation": "Taking the first element (3) and adding the sum of the remaining list ([1, 4]) forms a valid recursive step.",
            "hint": "Divide the input into a single processed element plus a strictly smaller sub-problem.",
        },
        {
            "step_number": 2,
            "total_steps": 3,
            "context": "sum_list([1, 4]) is now evaluated.",
            "prompt": "What is the next recursive step?",
            "options": {
                "a": "1 + sum_list([4])",
                "b": "1 + sum_list([1])",
                "c": "4 + sum_list([])",
            },
            "correct": "a",
            "explanation": "The head is 1, and the tail is [4]. This strictly shrinks the remaining input length from 2 to 1.",
            "hint": "Continue peeling off the head of the current slice.",
        },
        {
            "step_number": 3,
            "total_steps": 3,
            "context": "sum_list([]) hits the base case and returns 0.",
            "prompt": "How do the partial answers recombine to yield the final sum?",
            "options": {
                "a": "3 + (1 + (4 + 0)) = 8",
                "b": "0 + 1 + 3 = 4",
                "c": "3 * 1 * 4 = 12",
            },
            "correct": "a",
            "explanation": "Each waiting frame adds its head to the value returned by its callee: 4+0=4, then 1+4=5, then 3+5=8.",
            "hint": "Unwind backwards adding each saved head element.",
        },
    ],
    "return_propagation": [
        {
            "step_number": 1,
            "total_steps": 3,
            "context": "In power(2, 3), power(2, 0) hits the base case.",
            "prompt": "What is the initial return value created at the base case?",
            "options": {
                "a": "0",
                "b": "1",
                "c": "2",
            },
            "correct": "b",
            "explanation": "power(2, 0) returns 1 (since 2^0 = 1). This is the base return value that starts propagation.",
            "hint": "Any non-zero number raised to the power of 0 is 1.",
        },
        {
            "step_number": 2,
            "total_steps": 3,
            "context": "power(2, 0) returns 1 to power(2, 1).",
            "prompt": "What does power(2, 1) do with this returned value?",
            "options": {
                "a": "Multiplies it by x (2 * 1 = 2) and returns 2 to power(2, 2)",
                "b": "Discards it and calculates 2 * 3",
                "c": "Returns 1 directly to the user",
            },
            "correct": "a",
            "explanation": "power(2, 1) was paused at 'return 2 * power(2, 0)'. When power(2, 0) returns 1, it computes 2 * 1 = 2 and returns 2 to power(2, 2).",
            "hint": "The caller uses the returned value to complete its pending arithmetic expression.",
        },
        {
            "step_number": 3,
            "total_steps": 3,
            "context": "power(2, 2) receives 2 and returns 2 * 2 = 4 to power(2, 3).",
            "prompt": "What is the final value power(2, 3) propagates to the original caller?",
            "options": {
                "a": "2 * 4 = 8",
                "b": "4 + 2 = 6",
                "c": "1",
            },
            "correct": "a",
            "explanation": "power(2, 3) computes 2 * 4 = 8 and returns 8, completing the return propagation unwinding.",
            "hint": "The topmost caller performs the final multiplication.",
        },
    ],

    # ── Database Normalization ────────────────────────────────────────────────
    "first_normal_form": [
        {
            "step_number": 1,
            "total_steps": 3,
            "context": "A student table has a column 'Courses' containing 'CS101, MATH201, PHYS100'.",
            "prompt": "Why does this violate First Normal Form (1NF)?",
            "options": {
                "a": "The values in the Courses column are not atomic (they contain multiple items)",
                "b": "The table has no foreign keys",
                "c": "The column names are uppercase",
            },
            "correct": "a",
            "explanation": "1NF requires all attribute values to be atomic (indivisible single values per cell).",
            "hint": "Look for commas or repeating sets within a single field.",
        },
        {
            "step_number": 2,
            "total_steps": 3,
            "context": "To fix this, we split each course into a separate row.",
            "prompt": "What must we establish to ensure every row remains uniquely identifiable?",
            "options": {
                "a": "A composite primary key, such as (StudentID, CourseID)",
                "b": "A nullable column",
                "c": "An auto-incrementing text string",
            },
            "correct": "a",
            "explanation": "In 1NF, every record must have a unique identifier, often requiring a composite primary key when multi-valued attributes are separated into rows.",
            "hint": "Each row needs a distinct identifier so duplicate combinations cannot exist.",
        },
        {
            "step_number": 3,
            "total_steps": 3,
            "context": "Every attribute is now atomic, and each row has a defined primary key.",
            "prompt": "Which normal form requirement is now fully satisfied?",
            "options": {
                "a": "First Normal Form (1NF)",
                "b": "Third Normal Form (3NF)",
                "c": "Boyce-Codd Normal Form (BCNF)",
            },
            "correct": "a",
            "explanation": "Atomicity of attributes and unique row identification define 1NF.",
            "hint": "Atomicity is the defining milestone of 1NF.",
        },
    ],
    "second_normal_form": [
        {
            "step_number": 1,
            "total_steps": 3,
            "context": "Table Enrollment has composite primary key (StudentID, CourseID) and attribute CourseName.",
            "prompt": "Why is CourseName a partial dependency?",
            "options": {
                "a": "CourseName depends only on CourseID, which is just part of the composite primary key",
                "b": "CourseName depends on both StudentID and CourseID",
                "c": "CourseName has no relationship to CourseID",
            },
            "correct": "a",
            "explanation": "A partial dependency occurs when a non-prime attribute depends on a proper subset of a composite candidate key.",
            "hint": "Does knowing just the course allow you to know the course name?",
        },
        {
            "step_number": 2,
            "total_steps": 3,
            "context": "To achieve 2NF, we must eliminate partial dependencies.",
            "prompt": "How should we decompose the table?",
            "options": {
                "a": "Move (CourseID, CourseName) into an independent Courses table",
                "b": "Delete CourseName entirely from the database",
                "c": "Add InstructorName to the primary key",
            },
            "correct": "a",
            "explanation": "Decomposing into Enrollment(StudentID, CourseID) and Courses(CourseID, CourseName) eliminates the partial key dependency.",
            "hint": "Separate the attribute with its actual determinant into a dedicated relation.",
        },
        {
            "step_number": 3,
            "total_steps": 3,
            "context": "Every non-prime attribute now depends on the full primary key in both tables.",
            "prompt": "What normal form has been achieved?",
            "options": {
                "a": "Second Normal Form (2NF)",
                "b": "Unnormalized form",
                "c": "Fourth Normal Form (4NF)",
            },
            "correct": "a",
            "explanation": "A table is in 2NF if it is in 1NF and contains zero partial functional dependencies on candidate keys.",
            "hint": "Eliminating partial key dependencies yields 2NF.",
        },
    ],
    "third_normal_form": [
        {
            "step_number": 1,
            "total_steps": 3,
            "context": "Table Employee has PK EmpID, and attributes DepartmentID and DepartmentHead.",
            "prompt": "EmpID -> DepartmentID, and DepartmentID -> DepartmentHead. What kind of dependency is this?",
            "options": {
                "a": "Transitive functional dependency",
                "b": "Partial functional dependency",
                "c": "Trivial dependency",
            },
            "correct": "a",
            "explanation": "A non-prime attribute (DepartmentHead) depends on another non-prime attribute (DepartmentID), which in turn depends on the primary key.",
            "hint": "A -> B and B -> C means A -> C transitively.",
        },
        {
            "step_number": 2,
            "total_steps": 3,
            "context": "To satisfy 3NF, transitive dependencies must be removed.",
            "prompt": "How do we resolve the transitive dependency?",
            "options": {
                "a": "Create a separate Department(DepartmentID, DepartmentHead) table",
                "b": "Make DepartmentHead part of the EmpID key",
                "c": "Store DepartmentHead as a CSV list",
            },
            "correct": "a",
            "explanation": "Moving DepartmentID and DepartmentHead to a dedicated table removes the transitive dependency from Employee.",
            "hint": "Separate non-key determinants into their own tables.",
        },
        {
            "step_number": 3,
            "total_steps": 3,
            "context": "All attributes now depend directly on the primary key, the whole key, and nothing but the key.",
            "prompt": "Which normal form is satisfied?",
            "options": {
                "a": "Third Normal Form (3NF)",
                "b": "First Normal Form (1NF)",
                "c": "Zero Normal Form",
            },
            "correct": "a",
            "explanation": "3NF requires 2NF plus the complete absence of transitive dependencies on candidate keys.",
            "hint": "No non-key attribute depending on another non-key attribute means 3NF.",
        },
    ],
    "boyce_codd_normal_form": [
        {
            "step_number": 1,
            "total_steps": 3,
            "context": "In a relation R with functional dependency X -> Y, what must X be for R to be in BCNF?",
            "prompt": "What is the determinant requirement of BCNF?",
            "options": {
                "a": "X must be a candidate superkey",
                "b": "X can be any attribute",
                "c": "X must be a foreign key",
            },
            "correct": "a",
            "explanation": "BCNF strictly requires that for every non-trivial functional dependency X -> Y, X must be a superkey.",
            "hint": "Every determinant must be a candidate key.",
        },
        {
            "step_number": 2,
            "total_steps": 3,
            "context": "Given (Student, Course, Advisor) where (Student, Course) is PK, but Advisor -> Course.",
            "prompt": "Why does Advisor -> Course violate BCNF?",
            "options": {
                "a": "Advisor is a determinant, but it is not a candidate superkey for the relation",
                "b": "Advisor is a numeric column",
                "c": "Student is not unique",
            },
            "correct": "a",
            "explanation": "Advisor determines Course, but Advisor alone cannot identify a student or whole tuple, violating BCNF.",
            "hint": "Advisor determines another attribute without being a candidate key itself.",
        },
        {
            "step_number": 3,
            "total_steps": 3,
            "context": "We decompose into (Advisor, Course) and (Student, Advisor).",
            "prompt": "Are all determinants in both tables now candidate superkeys?",
            "options": {
                "a": "Yes, so both relations satisfy BCNF",
                "b": "No, BCNF is lost",
                "c": "Neither table has a key",
            },
            "correct": "a",
            "explanation": "In (Advisor, Course), Advisor is the key. In (Student, Advisor), (Student, Advisor) is the key. BCNF holds.",
            "hint": "Each sub-table now has a superkey determinant.",
        },
    ],
}


def get_guided_practice(
    concept: str,
    topic: str = "",
    settings: Settings | None = None,
) -> list[GuidedStep]:
    """Retrieve or synthesize a 3-step progressive Guided Practice sequence for a concept."""
    key = concept.lower().strip()
    if key in CURATED_GUIDED_PRACTICE:
        raw_steps = CURATED_GUIDED_PRACTICE[key]
        return [GuidedStep(**step) for step in raw_steps]

    # Topic-Agnostic fallback synthesis for generated or custom modules
    concept_title = concept.replace("_", " ").title()
    topic_str = f" in {topic}" if topic else ""

    return [
        GuidedStep(
            step_number=1,
            total_steps=3,
            context=f"Analyzing the baseline principles of {concept_title}{topic_str}.",
            prompt=f"Step 1: Identify the primary input condition or rule for {concept_title}.",
            options={
                "a": f"The explicit rules and constraints defining {concept_title}",
                "b": "An arbitrary unconstrained variable",
                "c": "No preconditions or constraints",
            },
            correct="a",
            explanation=f"{concept_title} requires identifying the core constraints and valid preconditions first.",
            hint=f"Focus on the fundamental rules governing {concept_title}.",
        ),
        GuidedStep(
            step_number=2,
            total_steps=3,
            context=f"Applying state transitions in {concept_title}.",
            prompt=f"Step 2: When applying {concept_title}, how does state transform?",
            options={
                "a": "It transforms deterministically according to the governing principles",
                "b": "It resets unexpectedly without trace",
                "c": "It halts execution immediately",
            },
            correct="a",
            explanation=f"Valid applications of {concept_title} produce consistent, predictable transitions.",
            hint="Trace the state change step by step.",
        ),
        GuidedStep(
            step_number=3,
            total_steps=3,
            context=f"Validating the final outcome of {concept_title}.",
            prompt=f"Step 3: What confirms that {concept_title} has been correctly resolved?",
            options={
                "a": "All constraints are satisfied and the expected output is achieved",
                "b": "The problem is skipped entirely",
                "c": "The execution raises an unhandled error",
            },
            correct="a",
            explanation=f"Success is verified when all specific constraints for {concept_title} hold true.",
            hint="Check that all criteria for success are met.",
        ),
    ]


# ── Fresh Retest Question Generation ──────────────────────────────────────────

# Independent question bank reserved specifically for Fresh Retests after Guided Practice
FRESH_RETEST_BANK: dict[str, RetestQuestion] = {
    # ── Python Recursion ──────────────────────────────────────────────────────
    "call_stack": RetestQuestion(
        concept="call_stack",
        text="When tracing a recursive tree for fib(4), what prevents the call stack from overflowing?",
        options={
            "a": "Each branch finishes and unwinds before the next sibling branch is pushed",
            "b": "All recursive calls execute in parallel on one frame",
            "c": "Python deletes past frames before the callee returns",
            "d": "Memory is unlimited in Python",
        },
        correct="a",
    ),
    "base_case": RetestQuestion(
        concept="base_case",
        text="In def binary_search(arr, low, high, x): if low > high: return -1, what role does 'low > high' serve?",
        options={
            "a": "Base case that signals the element is not present",
            "b": "Recursive step dividing the array",
            "c": "An error condition that crashes the interpreter",
            "d": "A helper function call",
        },
        correct="a",
    ),
    "recursive_step": RetestQuestion(
        concept="recursive_step",
        text="Given def reverse_str(s): if len(s) <= 1: return s; return reverse_str(s[1:]) + s[0], what is the recursive step?",
        options={
            "a": "reverse_str(s[1:]) + s[0]",
            "b": "len(s) <= 1",
            "c": "return s",
            "d": "s[0]",
        },
        correct="a",
    ),
    "return_propagation": RetestQuestion(
        concept="return_propagation",
        text="In def count_leaves(node): if not node: return 0; if not node.left and not node.right: return 1; return count_leaves(node.left) + count_leaves(node.right), how does the total propagate?",
        options={
            "a": "Return values from both children are summed and passed up to the parent node",
            "b": "Only the right child's return value reaches the root",
            "c": "The leaf nodes print the values without returning anything",
            "d": "The root computes the sum without waiting for child frames",
        },
        correct="a",
    ),

    # ── Database Normalization ────────────────────────────────────────────────
    "first_normal_form": RetestQuestion(
        concept="first_normal_form",
        text="A table has columns (EmployeeID, ProjectDetails) where ProjectDetails contains 'ProjectA:Lead, ProjectB:Tester'. To achieve 1NF, what must be done?",
        options={
            "a": "Decompose ProjectDetails into atomic columns (ProjectName, Role) across normalized rows",
            "b": "Encrypt the ProjectDetails string",
            "c": "Delete EmployeeID",
            "d": "Rename the table",
        },
        correct="a",
    ),
    "second_normal_form": RetestQuestion(
        concept="second_normal_form",
        text="In table OrderItem(OrderID, ProductID, UnitPrice, Quantity), where (OrderID, ProductID) is PK and ProductID -> UnitPrice, why does this violate 2NF?",
        options={
            "a": "UnitPrice depends only on ProductID, which is a partial key dependency",
            "b": "Quantity is not unique",
            "c": "OrderID is numeric",
            "d": "It violates 1NF atomicity",
        },
        correct="a",
    ),
    "third_normal_form": RetestQuestion(
        concept="third_normal_form",
        text="In table Student(StudentID, ZipCode, City, State), StudentID -> ZipCode and ZipCode -> (City, State). To achieve 3NF, what should be done?",
        options={
            "a": "Move (ZipCode, City, State) into a separate ZipDirectory table to eliminate transitive dependency",
            "b": "Make City and State part of the primary key",
            "c": "Store ZipCode as an integer",
            "d": "Keep everything in one table for performance",
        },
        correct="a",
    ),
    "boyce_codd_normal_form": RetestQuestion(
        concept="boyce_codd_normal_form",
        text="If a relation in 3NF has no composite candidate keys and only simple primary keys, does it automatically satisfy BCNF?",
        options={
            "a": "Yes, because non-trivial dependencies with non-superkey determinants cannot arise",
            "b": "No, BCNF is never satisfied by 3NF",
            "c": "Only if all attributes are strings",
            "d": "Only if the table has zero rows",
        },
        correct="a",
    ),
}


def get_fresh_retest_question(
    mod: CurriculumModule,
    concept: str,
    attempted_texts: set[str],
    settings: Settings | None = None,
) -> RetestQuestion:
    """Return an independent fresh retest question for a concept, avoiding all attempted questions."""
    # 1. First, check if there is an unused curated question in the bank
    unused = get_next_unused_retest_question(mod, concept, attempted_texts)
    if unused is not None:
        return unused

    # 2. Check the dedicated fresh retest bank
    key = concept.lower().strip()
    if key in FRESH_RETEST_BANK:
        fresh_q = FRESH_RETEST_BANK[key]
        if fresh_q.text.strip() not in attempted_texts:
            return fresh_q

    # 3. Dynamic synthesis fallback for arbitrary concepts
    concept_title = concept.replace("_", " ").title()
    topic_str = f" in {mod.title}" if mod.title else ""
    return RetestQuestion(
        concept=concept,
        text=f"Independent Assessment: Which of the following statements correctly applies the principles of {concept_title}{topic_str}?",
        options={
            "a": f"{concept_title} correctly enforces system invariants and valid state transitions.",
            "b": f"{concept_title} can be ignored without impacting correctness.",
            "c": f"{concept_title} only applies when no data or parameters are provided.",
            "d": f"{concept_title} halts execution unpredictably.",
        },
        correct="a",
    )


# ── Guided Practice Persistence & History ─────────────────────────────────────

def has_completed_guided_practice(store: Store, run_id: str, concept: str) -> bool:
    """Check if Guided Practice was already completed for this concept in this run."""
    history = store.history(run_id, "guided_practice")
    for v in history:
        payload = v.payload
        if payload.get("concept") == concept and payload.get("completed", False):
            return True
    return False


def get_guided_practice_progress(store: Store, run_id: str, concept: str) -> dict[str, Any] | None:
    """Get the latest guided practice record for concept, or None if not started."""
    history = store.history(run_id, "guided_practice")
    relevant = [v.payload for v in history if v.payload.get("concept") == concept]
    return relevant[-1] if relevant else None


def record_guided_practice_event(
    store: Store,
    run_id: str,
    student_id: str,
    concept: str,
    completed: bool,
    step_results: list[dict[str, Any]],
    current_step: int = 1,
    total_steps: int = 3,
) -> None:
    """Append a guided practice execution record to the immutable store history."""
    rec = GuidedPracticeRecord(
        student_id=student_id,
        concept=concept,
        completed=completed,
        current_step=current_step,
        total_steps=total_steps,
        step_results=step_results,
    )
    store.append(run_id, "guided_practice", rec.model_dump(), produced_by="system")
