from graph.state import AgentGraph


def submission_node(state: AgentGraph) -> dict:
    """
    Initial submission node.

    Receives the user's brief idea and starts the workflow.
    """

    return {
        "status": "STARTED",
        "current_node": "Submission",
        "revision_count": 0,
        "decision_history": [],
        "draft_versions": [],
        "node_history": [],
    }


def classify_node(state: AgentGraph) -> dict:
    """
    Classifies the idea into one predefined category
    and produces a confidence score.

    Actual LLM implementation will be added later.
    """

    return {
        "classification": {
            "category": "",
            "confidence": 0.0,
        },
        "status": "CLASSIFIED",
        "current_node": "Classify",
    }


def duplicate_check_node(state: AgentGraph) -> dict:
    """
    Checks whether the submitted idea is already present
    or semantically similar to existing ideas.

    Actual SQL Server + embedding implementation
    will be added later.
    """

    return {
        "duplicate_matches": [],
        "duplicate_found": False,
        "status": "DUPLICATE_CHECKED",
        "current_node": "Duplicate Check",
    }


def enrich_node(state: AgentGraph) -> dict:
    """
    Enriches the idea using available information.

    On the first pass, it enriches the original idea.

    On later passes, it also uses reviewer feedback
    to help the user improve the draft.
    """

    feedback = state.get("reviewer_feedback", "")

    if feedback:
        # Later this will use the feedback
        # to produce better enrichment context.
        pass

    return {
        "enrichment": {},
        "status": "ENRICHED",
        "current_node": "Enrich",
    }


def draft_summary_node(state: AgentGraph) -> dict:
    """
    Gets the draft summary from the user.

    IMPORTANT:
    The user provides/modifies the draft.
    This node should eventually pause the graph and
    wait for user input.
    """

    return {
        "draft_summary": "",
        "status": "DRAFT_RECEIVED",
        "current_node": "Draft Summary",
    }


def human_approval_node(state: AgentGraph) -> dict:
    """
    Human review point.

    Possible actions:

        reject
        send_back
        accept

    Actual interrupt() implementation will be added later.
    """

    return {
        "status": "WAITING_FOR_APPROVAL",
        "current_node": "Human Approval",
    }


def finalize_node(state: AgentGraph) -> dict:
    """
    Finalizes an accepted idea.
    """

    return {
        "status": "ACCEPTED",
        "current_node": "Finalize",
    }