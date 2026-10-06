from typing import Literal

from graph.state import AgentGraph


QUALITY_THRESHOLD = 0.70


def route_after_classification(
    state: AgentGraph,
) -> Literal[
    "reject",
    "pass",
]:

    idea_score = (
        state["idea_assessment"]["idea_score"]
    )

    if idea_score < QUALITY_THRESHOLD:
        return "low_score"

    return "pass"


def route_after_duplicate_check(
    state: AgentGraph,
) -> Literal[
    "duplicate",
    "not_duplicate",
]:

    if state.get(
        "duplicate_found",
        False,
    ):

        return "duplicate"

    return "not_duplicate"


def route_after_approval(
    state: AgentGraph,
) -> Literal[
    "reject",
    "improve",
    "approve",
]:

    decision = state.get(
        "current_decision"
    )

    if not decision:
        raise ValueError(
            "Human decision is missing"
        )

    action = decision.get("action")

    if action == "reject":
        return "reject"

    if action == "improve":
        return "improve"

    if action == "approve":
        return "approve"

    raise ValueError(
        f"Invalid human decision: {action}"
    )