from langgraph.types import interrupt

from graph.state import AgentGraph


def human_approval_node(
    state: AgentGraph,
) -> dict:

    node_name = "Human Approval"

    decision = interrupt(
        {
            "message": (
                "Do you want to approve the idea, "
                "reject the idea, or request improvements?"
            ),
            "options": [
                "approve",
                "reject",
                "improve",
            ],
        }
    )

    action = decision.get("action")

    comment = decision.get(
        "comment",
        "",
    )

    if action not in {
        "approve",
        "reject",
        "improve",
    }:

        raise ValueError(
            f"Invalid human decision: {action}"
        )

    return {
        "current_decision": {
            "action": action,
            "comment": comment,
        },

        "reviewer_feedback": comment,

        "current_node": node_name,

        "status": "HUMAN_DECISION",
    }