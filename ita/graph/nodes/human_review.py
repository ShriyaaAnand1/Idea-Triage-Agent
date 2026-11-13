from graph.state import AgentGraph


def human_review_node(state: AgentGraph) -> dict:

    return {
        "current_node": "Human Review",
        "status": "HUMAN_REVIEW"
    }