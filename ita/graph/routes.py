from langgraph.graph import END
from graph.state import AgentGraph

CONFIDENCE_THRESHOLD = 0.70

def route_after_classification(state: AgentGraph) -> str:

    confidence = state["classification"]["confidence"]
    if confidence < CONFIDENCE_THRESHOLD:
        return END
    return "Duplicate Check"


def route_after_duplicate_check(state: AgentGraph) -> str:
    if state["duplicate_found"]:
        return END
    return "Enrich"


def route_after_approval(state: AgentGraph) -> str:
    decision = state["current_decision"]["action"]
    if decision == "reject":
        return END
    if decision == "send_back":
        return "Enrich"
    if decision == "accept":
        return "Finalize"
    raise ValueError(
        f"Unknown approval decision: {decision}"
    )