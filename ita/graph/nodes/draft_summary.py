from graph.state import AgentGraph


def draft_summary_node(
    state: AgentGraph,
) -> dict:

    node_name = "Draft Summary"

    print("\n========== DRAFT SUMMARY ==========")

    print("\nEnter the summary of the idea:")

    draft = input("> ").strip()

    if not draft:
        raise ValueError(
            "Draft summary cannot be empty"
        )

    print("\nDraft summary received.")

    print("===================================\n")

    return {
        "draft_summary": draft,
        "current_node": node_name,
        "status": "DRAFT_CREATED",
    }