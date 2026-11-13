
from langgraph.types import interrupt

from graph.state import AgentGraph
from database.approvals import create_approval
from database.connection import db_connection


VALID_ACTIONS = {"approve", "reject", "improve"}


def get_active_task_id(thread_id: str) -> str:
    """Find the latest draft submitted for this workflow."""
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT TOP 1 task_id
                FROM dbo.Runs
                WHERE thread_id = ?
                ORDER BY started_at DESC, task_id DESC
                """,
                (thread_id,),
            )
            row = cursor.fetchone()

            if row is None or row[0] is None:
                raise ValueError(
                    f"No submitted draft exists for thread_id={thread_id}"
                )

            return str(row[0])
        finally:
            cursor.close()


def human_approval_node(state: AgentGraph) -> dict:
    thread_id = str(state.get("thread_id") or "").strip()

    if not thread_id:
        raise ValueError(
            "Human Approval requires thread_id in graph state."
        )

    # The database, not the checkpoint, identifies the active draft.
    task_id = get_active_task_id(thread_id)

    create_approval(
        thread_id=thread_id,
        task_id=task_id,
    )

    decision = interrupt(
        {
            "type": "approval_required",
            "thread_id": thread_id,
            "message": (
                "A reviewer decision is required for this draft summary."
            ),
            "options": ["approve", "reject", "improve"],
        }
    )

    if not isinstance(decision, dict):
        raise ValueError(
            "Expected a dictionary containing action and comment."
        )

    action = str(decision.get("action") or "").strip().lower()
    comment = str(decision.get("comment") or "").strip()

    if action not in VALID_ACTIONS:
        raise ValueError(
            "Reviewer action must be approve, reject, or improve."
        )

    if action == "improve" and not comment:
        raise ValueError(
            "A comment is required when choosing improve."
        )

    decision_history = list(state.get("decision_history") or [])
    decision_history.append({
        "task_id": task_id,
        "thread_id": thread_id,
        "action": action.upper(),
        "comment": comment or None,
    })

    return {
        "thread_id": thread_id,
        "current_node": "Human Approval",
        "current_decision": action,
        "reviewer_decision": action.upper(),
        "reviewer_feedback": comment or None,
        "decision_history": decision_history,
        "status": "HUMAN_DECISION",
    }
