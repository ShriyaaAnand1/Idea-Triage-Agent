from langgraph.graph import StateGraph, START, END

from graph.state import AgentGraph

from graph.nodes import (
    submission_node,
    classify_node,
    duplicate_check_node,
    enrich_node,
    draft_summary_node,
    human_approval_node,
    finalize_node,
)

from graph.routes import (
    route_after_classification,
    route_after_duplicate_check,
    route_after_approval,
)


builder = StateGraph(AgentGraph)

builder.add_node("Submission", submission_node)
builder.add_node("Classify",  classify_node)
builder.add_node("Duplicate Check", duplicate_check_node)
builder.add_node("Enrich",  enrich_node)
builder.add_node( "Draft Summary", draft_summary_node)
builder.add_node( "Human Approval",human_approval_node)
builder.add_node(  "Finalize",  finalize_node)


builder.add_edge(  START,"Submission")
builder.add_edge("Submission","Classify")



builder.add_conditional_edges(
    "Classify",
    route_after_classification,
    {
        "Duplicate Check": "Duplicate Check",
        END: END,
    }
)


builder.add_conditional_edges(
    "Duplicate Check",
    route_after_duplicate_check,
    {
        "Enrich": "Enrich",
        END: END,
    }
)

# Enrichment → Draft → HITL
builder.add_edge(
    "Enrich","Draft Summary"
)

builder.add_edge( "Draft Summary", "Human Approval")

builder.add_conditional_edges(
    "Human Approval",
    route_after_approval,
    {
        # Reviewer asks user to modify
        # → go through enrichment again
        "Enrich": "Enrich",

        # Reviewer accepts
        "Finalize": "Finalize",

        # Reviewer rejects
        END: END,
    }
)
builder.add_edge("Finalize", END)

graph = builder.compile()