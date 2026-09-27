from typing import Literal

from graph.state import AgentGraph


QUALITY_THRESHOLD = 0.70


def route_after_classification(
    state: AgentGraph,
) -> Literal["low_score", "pass"]:

    idea_score = state["idea_assessment"]["idea_score"]

    if idea_score < QUALITY_THRESHOLD:
        return "low_score"

    return "pass"


def route_after_duplicate_check(
    state: AgentGraph,
) -> Literal["duplicate", "not_duplicate"]:

    if state.get("is_duplicate", False):
        return "duplicate"

    return "not_duplicate"


def route_after_approval(
    state: AgentGraph,
) -> Literal["reject", "feedback", "approve"]:

    decision = state.get("approval_decision")

    if decision == "reject":
        return "reject"

    if decision == "feedback":
        return "feedback"

    if decision == "approve":
        return "approve"

    raise ValueError(
        f"Invalid approval decision: {decision}"
    )