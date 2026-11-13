from pydantic import BaseModel, Field
from typing import Optional

class IdeaRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=255)
    idea: str = Field(min_length=10)


class DraftSummaryRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=255)
    thread_id: str = Field(min_length=1, max_length=255)
    task_id: Optional[str] = None
    draft_summary: str = Field(min_length=1)


class DecisionRequest(BaseModel):
    task_id: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1, max_length=255)
    action: str
    comment: Optional[str] = None