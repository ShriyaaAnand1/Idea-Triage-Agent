from graph.state import AgentGraph


def human_approval_node(state: AgentGraph) -> dict:

    print("\n========== HUMAN APPROVAL ==========")

    draft = state.get("draft")

    print("\nDraft Summary:")
    print(draft)

    print("\nChoose a decision:")
    print("1. approve")
    print("2. reject")
    print("3. feedback")

    decision = input("\nDecision: ").strip().lower()

    if decision not in {
        "approve",
        "reject",
        "feedback",
    }:

        raise ValueError(
            "Decision must be approve, reject, or feedback"
        )

    feedback = None

    if decision == "feedback":

        feedback = input(
            "\nEnter reviewer feedback: "
        ).strip()

        if not feedback:
            raise ValueError(
                "Feedback cannot be empty"
            )

    print("\nDecision:", decision)

    if feedback:
        print("Feedback:", feedback)

    print("====================================\n")

    return {
        "approval_decision": decision,
        "approval_feedback": feedback,
        "current_node": "Human Approval",
        "status": "HUMAN_DECISION",
    }