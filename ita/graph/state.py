from typing import TypedDict, Dict, Any, List, Optional


class Classification(TypedDict):
    category:str
    confidence_value:float

class Duplicate(TypedDict):
    idea_id:str
    text:str
    similarity:float

class Decision(TypedDict):
    reviewer_id:str
    action:str
    comment:str
    timestamp:str
    duration:str

class DraftVersion(TypedDict):
    version:int
    content:str
    created_at:str

class NodeHistory(TypedDict):
    Node:str
    start:str
    finish:str
    duration:str
    input:Dict[str,Any]
    output:Dict[str,Any]

class AgentGraph(TypedDict):
    # Basic workflow information
    run_id: str
    thread_id: str
    correlation_id: str
    current_node: str
    status: str

    # User submission
    submission: str

    # Classification

    classification: Classification

    # Duplicate detection

    duplicate_matches: List[Duplicate]
    duplicate_found: bool

    # Enrichment
    enrichment: Dict[str, Any]

    # Draft
    draft_summary: str
    draft_versions: List[DraftVersion]

    # HITL

    current_decision: Optional[Decision]
    decision_history: List[Decision]

    # Feedback from reviewer
    reviewer_feedback: str

    # Iteration
    revision_count: int

    # Node execution tracking
    node_history: List[Dict[str, Any]]
