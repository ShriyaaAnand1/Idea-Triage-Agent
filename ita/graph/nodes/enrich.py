from graph.state import AgentGraph


def enrich_node(
    state: AgentGraph,
) -> dict:

    node_name = "Enrich"

    feedback = state.get(
        "reviewer_feedback",
        "",
    )

    if not feedback:
        raise ValueError(
            "Improvement feedback is required"
        )

    print("\n========== ENRICH ==========")

    print("\nImprovement requested:")
    print(feedback)

    print("\n============================\n")

    return {
        "enrichment": {
            "feedback": feedback
        },

        "current_node": node_name,

        "status": "ENRICHED",
    }