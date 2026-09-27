from graph.state import AgentGraph


def draft_summary_node(state: AgentGraph) -> dict:

    print("\n========== DRAFT SUMMARY ==========")

    submission = state.get("submission")

    print("\nOriginal Idea:")
    print(submission)

    print("\nEnter the draft summary for this idea:")

    draft = input("> ").strip()

    if not draft:
        raise ValueError(
            "Draft summary cannot be empty"
        )

    print("\nDraft summary received.")

    print("===================================\n")

    return {
        "draft": draft,
        "current_node": "Draft Summary",
        "status": "DRAFT_CREATED",
    }