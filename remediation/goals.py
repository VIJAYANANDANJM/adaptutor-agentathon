"""
remediation/goals.py — Clear, concept-specific learning goals and achievements.

Provides concrete, pedagogical learning targets for each concept to make
it immediately obvious to the student what they need to understand next.
"""
from __future__ import annotations

CONCEPT_GOALS: dict[str, dict[str, str]] = {
    # ── Python Recursion ───────────────────────────────────────────────────
    "call_stack": {
        "goal": "Understand how function calls are added to the call stack and why the caller resumes only after the recursive call completes.",
        "achieved": "You can now trace stack frame accumulation and return unwinding.",
    },
    "base_case": {
        "goal": "Identify non-recursive termination conditions that stop execution loops.",
        "achieved": "You can now identify base cases and prevent infinite recursion.",
    },
    "recursive_step": {
        "goal": "Understand how to decompose a problem into smaller self-referential sub-problems that converge toward the base case.",
        "achieved": "You can now formulate recursive transitions that make steady progress.",
    },
    "return_propagation": {
        "goal": "Trace how return values pass back up through pending caller frames to construct the final result.",
        "achieved": "You can now explain recursive return value propagation up the call stack.",
    },

    # ── Database Management: Relational Normalization ──────────────────────
    "first_normal_form": {
        "goal": "Identify repeating groups and ensure all attribute values are atomic and properly keyed.",
        "achieved": "You can now enforce atomicity and eliminate repeating groups for 1NF.",
    },
    "second_normal_form": {
        "goal": "Identify and remove partial functional dependencies on composite primary keys.",
        "achieved": "You can now eliminate partial key dependencies to achieve 2NF.",
    },
    "third_normal_form": {
        "goal": "Eliminate transitive functional dependencies where non-key attributes depend on other non-key attributes.",
        "achieved": "You can now eliminate transitive functional dependencies to satisfy 3NF.",
    },
    "boyce_codd_normal_form": {
        "goal": "Ensure that every determinant in a functional dependency is a candidate superkey.",
        "achieved": "You can now verify strict superkey determinants for BCNF.",
    },

    # ── OS Virtual Memory ──────────────────────────────────────────────────
    "operating_systems_virtual_fundamentals": {
        "goal": "Understand the decoupling of virtual address spaces from physical memory frames.",
        "achieved": "You can now explain virtual-to-physical address translation.",
    },
    "operating_systems_virtual_core_rules": {
        "goal": "Master page table structures, page faults, and TLB lookup mechanics.",
        "achieved": "You can now trace page hits, page faults, and TLB caching.",
    },
    "operating_systems_virtual_edge_cases": {
        "goal": "Analyze page replacement algorithms, working set models, and thrashing prevention.",
        "achieved": "You can now resolve memory overcommit and thrashing scenarios.",
    },
    "operating_systems_virtual_advanced_flow": {
        "goal": "Evaluate hierarchical multi-level paging and inverted page table performance.",
        "achieved": "You can now evaluate hierarchical page table architectures.",
    },

    # ── IoT MQTT ───────────────────────────────────────────────────────────
    "iot_mqtt_fundamentals": {
        "goal": "Understand publish/subscribe architecture and broker message decoupling.",
        "achieved": "You can now design decoupled MQTT publisher/subscriber topologies.",
    },
    "iot_mqtt_core_rules": {
        "goal": "Distinguish MQTT Quality of Service (QoS 0, QoS 1, QoS 2) delivery guarantees.",
        "achieved": "You can now select appropriate QoS levels for constrained IoT networks.",
    },
    "iot_mqtt_edge_cases": {
        "goal": "Manage keep-alive intervals, broker disconnects, and Last Will and Testament (LWT).",
        "achieved": "You can now handle abrupt client disconnections using LWT and retain flags.",
    },
    "iot_mqtt_advanced_flow": {
        "goal": "Configure wildcard topic subscriptions (+, #) and payload security.",
        "achieved": "You can now architect secure, scalable topic subscription hierarchies.",
    },
}


def get_learning_goal(concept: str, topic: str = "", attempt: int = 1) -> str:
    """Return a specific, pedagogically grounded learning goal for a concept."""
    key = concept.lower().strip()
    if key in CONCEPT_GOALS:
        return CONCEPT_GOALS[key]["goal"]

    # Dynamic goal synthesis for arbitrary AI-generated modules
    concept_title = concept.replace("_", " ").title()
    topic_str = f" in {topic}" if topic else ""
    return f"Master the core rules, constraints, and valid implementations of {concept_title}{topic_str}."


def get_goal_achieved(concept: str, topic: str = "") -> str:
    """Return an achievement confirmation message after passing a retest."""
    key = concept.lower().strip()
    if key in CONCEPT_GOALS:
        return CONCEPT_GOALS[key]["achieved"]

    concept_title = concept.replace("_", " ").title()
    return f"You can now correctly apply and explain the principles of {concept_title}."
