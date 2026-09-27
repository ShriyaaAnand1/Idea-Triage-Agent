from graph.state import AgentGraph


def finalize_node(
    state: AgentGraph,
) -> dict:

    node_name = "Finalize"

    print("\n========== FINALIZE ==========")

    print("\nIdea approved successfully.")

    print("\nFinal Summary:")
    print(
        state.get(
            "draft_summary",
            ""
        )
    )

    print("\n==============================\n")

    return {
        "current_node": node_name,
        "status": "FINALIZED",
    }