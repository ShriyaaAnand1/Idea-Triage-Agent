from langgraph.graph import StateGraph, START, END
from database.connection import get_checkpointer
from graph.state import AgentGraph

from graph.nodes.submission import submission_node
from graph.nodes.classify import classify_node
from graph.nodes.human_review import human_review_node
from graph.nodes.duplicate_check import duplicate_check_node
from graph.nodes.enrich import enrich_node
from graph.nodes.draft_summary import draft_summary_node
from graph.nodes.human_approval import human_approval_node
from graph.nodes.finalize import finalize_node

from graph.routes import (
    route_after_classification,
    route_after_duplicate_check,
    route_after_approval,
)


builder = StateGraph(AgentGraph)


builder.add_node( "Submission", submission_node)

builder.add_node("Classify",classify_node)

builder.add_node("Human Review",human_review_node)

builder.add_node("Duplicate Check",duplicate_check_node)

builder.add_node("Draft Summary", draft_summary_node)

builder.add_node("Human Approval",human_approval_node)

builder.add_node( "Enrich",enrich_node)

builder.add_node("Finalize", finalize_node)


builder.add_edge( START, "Submission")

builder.add_edge("Submission","Classify")


builder.add_conditional_edges(
    "Classify",
    route_after_classification,
    {
        "low_score": "Human Review",
        "pass": "Duplicate Check",
    }
)

builder.add_edge( "Human Review", END)

builder.add_conditional_edges(
    "Duplicate Check",
    route_after_duplicate_check,
    {
        "duplicate": END,
        "not_duplicate": "Draft Summary",
    }
)


builder.add_edge( "Draft Summary", "Human Approval")


builder.add_conditional_edges(
    "Human Approval",
    route_after_approval,
    {
        "reject": END,
        "improve": "Enrich",
        "approve": "Finalize",
    }
)


builder.add_edge( "Enrich","Draft Summary")

builder.add_edge( "Finalize", END)

def create_graph(checkpointer):
    return builder.compile(
        checkpointer=checkpointer
    )