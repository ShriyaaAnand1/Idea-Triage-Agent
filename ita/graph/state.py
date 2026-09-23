from typing import TypedDict, Dict, Any, List, Optional

class Classification(TypedDict):
    category: str

class IdeaAssessment(TypedDict):
    idea_score: float
    scores: Dict[str, float]
    reason: str

class DuplicateMatch(TypedDict):
    idea_id:str
    submission:str
    similarity:float

class Decision(TypedDict):
    reviewer_id:str
    action:str
    comment:str
    timestamp:str
    duration_ms:str

class DraftVersion(TypedDict):
    version:int
    content:str
    created_at:str

class NodeHistoryEntry(TypedDict):
    node: str
    run_id: str
    correlation_id: str

    input: Dict[str, Any]
    output: Dict[str, Any]

    started_at: str
    finished_at: str
    duration_ms: float

    success: bool
    error_type: Optional[str]
    error_message: Optional[str]

    previous_node: Optional[str]
    next_node: Optional[str]

class AgentGraph(TypedDict, total=False):
    run_id: str
    thread_id: str
    correlation_id: str

    current_node: str
    status: str

    submission: str

    classification: Classification
    idea_assessment: IdeaAssessment

    duplicate_matches: List[DuplicateMatch]
    duplicate_found: bool

    enrichment: Dict[str, Any]

    draft_summary: str
    draft_versions: List[DraftVersion]

    current_decision: Optional[Decision]
    decision_history: List[Decision]

    reviewer_feedback: str

    revision_count: int

    node_history: List[NodeHistoryEntry]
