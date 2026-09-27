from graph.state import AgentGraph


def submission_node(state: AgentGraph) -> dict:

    node_name = "Submission"

    submission = state.get("submission")

    if not submission:
        raise ValueError(
            "Submission cannot be empty"
        )

    print("\n========== SUBMISSION ==========")

    print("\nIdea submitted:")
    print(submission)

    print("\n================================")

    return {
        "current_node": node_name,
        "status": "SUBMITTED",
    }