import json
from typing import Any, Optional

from database.queries import execute_sql
from logger.logging import logger
from graph.workflow import get_checkpointer, create_graph

DRAFT_INTERRUPT = "draft_summary_required"
APPROVAL_INTERRUPT = "approval_required"

def graph_config(thread_id: str) -> dict:
    return {
        "configurable": {
            "thread_id": str(thread_id)
        }
    }


def get_graph():
    context = get_checkpointer()
    checkpointer = context.__enter__()

    try:
        return create_graph(checkpointer), context
    except Exception as exc:
        context.__exit__(type(exc), exc, exc.__traceback__)
        raise


def close_graph_context(context) -> None:
    context.__exit__(None, None, None)


def get_interrupt_payload(
    snapshot,
    expected_type: Optional[str] = None,
) -> Optional[dict]:
    matches = []

    for task in getattr(snapshot, "tasks", ()) or ():
        for interrupt_item in getattr(task, "interrupts", ()) or ():
            value = getattr(interrupt_item, "value", None)

            if not isinstance(value, dict):
                continue

            if (
                expected_type is None
                or value.get("type") == expected_type
            ):
                matches.append(value)

    return matches[-1] if matches else None


def snapshot_is_complete(snapshot) -> bool:
    return not bool(getattr(snapshot, "next", ()))


def status_from_snapshot(snapshot):
    values = dict(getattr(snapshot, "values", {}) or {})
    payload = get_interrupt_payload(snapshot)

    interrupt_type = payload.get("type") if payload else None
    complete = snapshot_is_complete(snapshot)

    if interrupt_type == DRAFT_INTERRUPT:
        status = "AWAITING_DRAFT_SUMMARY"

    elif interrupt_type == APPROVAL_INTERRUPT:
        status = "AWAITING_APPROVAL"

    elif complete:
        status = str(
            values.get("status") or "COMPLETED"
        ).upper()

    else:
        status = str(
            values.get("status") or "IN_PROGRESS"
        ).upper()

    return status, interrupt_type, values, payload, complete

def update_run_from_snapshot(
    fallback_task_id: Optional[str],
    snapshot,
) -> dict:
    """
    Update the Run identified by the supplied database/API Task ID.

    Do not read task_id from checkpoint values to determine which
    Runs record should be updated.
    """
    (
        status,
        interrupt_type,
        values,
        payload,
        complete,
    ) = status_from_snapshot(snapshot)

    task_id = (
        str(fallback_task_id)
        if fallback_task_id
        else None
    )

    thread_id = str(values.get("thread_id") or "")
    current_node = values.get("current_node")

    if task_id and thread_id:
        affected = execute_sql(
            """
            UPDATE dbo.Runs
            SET status = ?,
                current_node = ?,
                completed_at = CASE
                    WHEN ? = 1
                        THEN COALESCE(
                            completed_at,
                            SYSUTCDATETIME()
                        )
                    ELSE NULL
                END
            WHERE task_id = ?
              AND thread_id = ?
            """,
            (
                status,
                current_node,
                int(complete),
                task_id,
                thread_id,
            ),
        )

        if affected != 1:
            logger.warning(
                "Expected one Runs row; updated %s. "
                "task_id=%s thread_id=%s",
                affected,
                task_id,
                thread_id,
            )

    if thread_id:
        execute_sql(
            """
            UPDATE dbo.Ideas
            SET status = ?
            WHERE thread_id = ?
            """,
            (status, thread_id),
        )

    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "status": status,
        "current_node": current_node,
        "submission": values.get("submission"),
        "classification": values.get("classification"),
        "idea_assessment": values.get("idea_assessment"),
        "duplicate_found": values.get("duplicate_found"),
        "duplicate_matches": values.get(
            "duplicate_matches", []
        ),
        "draft_summary": values.get("draft_summary"),
        "draft_versions": values.get("draft_versions", []),
        "reviewer_feedback": values.get("reviewer_feedback"),
        "reviewer_decision": (
            values.get("reviewer_decision")
            or values.get("current_decision")
        ),
        "needs_draft_summary": (
            interrupt_type == DRAFT_INTERRUPT
        ),
        "needs_approval": (
            interrupt_type == APPROVAL_INTERRUPT
        ),
        "is_complete": complete,
    }



def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(value, default=str, ensure_ascii=False)
    )
