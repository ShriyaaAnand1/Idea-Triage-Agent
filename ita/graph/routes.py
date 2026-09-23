from graph.state import AgentGraph

CONFIDENCE_THRESHOLD = 0.70

def route_after_classification( state: AgentGraph) -> str:

    confidence = state[ "classification" ][ "confidence" ]
    if confidence < CONFIDENCE_THRESHOLD:
        return "Manual Review"

    return "Duplicate Check"

