
from datetime import datetime, timezone
from langgraph.types import interrupt
from uuid import uuid4

from graph.state import AgentGraph


def draft_summary_node(state: AgentGraph) -> dict:
    """
    Pause for the user's draft summary.

    The first task_id is generated when the user submits the first draft.
    On subsequent revisions, a new task_id is generated for each review cycle.
    The thread_id remains unchanged for the entire idea workflow.
    """

    thread_id = str(state.get("thread_id") or "").strip()
    user_id = str(state.get("user_id") or "").strip()
    current_task_id = str(state.get("task_id") or "").strip()

    if not thread_id:
        raise ValueError("Draft Summary requires thread_id in graph state.")

    if not user_id:
        raise ValueError("Draft Summary requires user_id in graph state.")

    # Pause and request the user's draft.
    submitted_summary = interrupt(
        {
            "type": "draft_summary_required",
            "task_id": current_task_id or None,
            "thread_id": thread_id,
            "user_id": user_id,
            "message": "Please submit or revise the draft summary.",
        }
    )

    if not isinstance(submitted_summary, str):
        raise ValueError("The submitted draft summary must be text.")

    submitted_summary = submitted_summary.strip()

    if not submitted_summary:
        raise ValueError("The submitted draft summary cannot be empty.")

    # Create a task ID for this review cycle.
    # First draft: T1. Revised draft: T2, T3, etc.
    # The API should pass the newly generated ID through graph state
    # before resuming this interrupt.
    task_id = current_task_id or str(uuid4())

    now = datetime.now(timezone.utc).isoformat()

    draft_versions = list(state.get("draft_versions") or [])
    revision_count = int(state.get("revision_count") or 0) + 1

    draft_versions.append(
        {
            "version": revision_count,
            "content": submitted_summary,
            "created_at": now,
            "task_id": task_id,
        }
    )

    return {
        "user_id": user_id,
        "task_id": task_id,
        "thread_id": thread_id,
        "draft_summary": submitted_summary,
        "draft_versions": draft_versions,
        "revision_count": revision_count,
        "current_node": "Draft Summary",
        "status": "DRAFT_CREATED",
    }