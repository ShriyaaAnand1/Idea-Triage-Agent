from services.workflow_service import get_graph,graph_config,close_graph_context,get_interrupt_payload,update_run_from_snapshot,json_safe
from database.queries import execute_sql,fetch_all,fetch_one
from database.users import validate_user
from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from routes.schema import  DecisionRequest
from database.connection import db_connection
from database.runs import get_latest_run_for_thread
from logger.logging import logger

APPROVAL_INTERRUPT = "approval_required"
VALID_ACTIONS = {"APPROVE", "REJECT", "IMPROVE"}

reviewer_router=APIRouter(prefix="/reviewer",tags=["Reviewer"])


def reviewer_approval_rows(
    reviewer_id: str,
    queue_type: str,
) -> list[dict]:

    validate_user(
        reviewer_id.strip(),
        "REVIEWER",
    )

    if queue_type == "pending":
        filter_sql = (
            "a.status = 'PENDING' AND a.escalated = 0"
        )

    elif queue_type == "escalated":
        filter_sql = (
            "a.escalated = 1 "
            "AND a.status IN ('PENDING', 'ESCALATED')"
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Unknown reviewer queue.",
        )

    rows = fetch_all(
        f"""
        SELECT
            a.task_id AS task_id,
            a.thread_id AS thread_id,
            r.user_id AS user_id,
            r.status AS run_status,
            r.current_node AS current_node,
            a.status AS approval_status,
            a.action AS action,
            a.reviewer_id AS reviewer_id,
            a.requested_at AS requested_at,
            a.responded_at AS responded_at,
            a.escalated AS escalated,
            a.escalated_at AS escalated_at
        FROM dbo.Approvals AS a
        INNER JOIN dbo.Runs AS r
            ON r.task_id = a.task_id
           AND r.thread_id = a.thread_id
        WHERE {filter_sql}
        ORDER BY a.requested_at ASC
        """
    )

    approvals = []

    for row in rows:
        task_id = str(row["task_id"])
        thread_id = str(row["thread_id"])
        user_id = str(row["user_id"])

        graph, context = get_graph()

        try:
            snapshot = graph.get_state(
                graph_config(thread_id)
            )
            payload = get_interrupt_payload(
                snapshot,
                APPROVAL_INTERRUPT,
            )
            # Only an active approval interrupt is actionable.
            if payload is None:
                continue
            checkpoint_values = dict(
                getattr(snapshot, "values", {}) or {}
            )
            checkpoint_thread_id = str(
                checkpoint_values.get("thread_id") or ""
            )

            if checkpoint_thread_id != thread_id:
                logger.warning(
                    "Skipping approval with mismatched thread: "
                    "task_id=%s approval_thread=%s checkpoint_thread=%s",
                    task_id,
                    thread_id,
                    checkpoint_thread_id,
                )
                continue

            # Validate against SQL, not payload["task_id"].
            latest_run = get_latest_run_for_thread(
                thread_id,
                user_id,
            )

            if latest_run is None:
                continue

            latest_task_id = str(latest_run["task_id"])

            if latest_task_id != task_id:
                logger.warning(
                    "Skipping stale approval task_id=%s "
                    "latest_task_id=%s thread_id=%s",
                    task_id,
                    latest_task_id,
                    thread_id,
                )
                continue

            approvals.append(
                json_safe({
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "run_status": row["run_status"],
                    "current_node": row["current_node"],
                    "status": row["approval_status"],
                    "action": row["action"],
                    "reviewer_id": row["reviewer_id"],
                    "requested_at": row["requested_at"],
                    "responded_at": row["responded_at"],
                    "escalated": bool(row["escalated"]),
                    "escalated_at": row["escalated_at"],
                    "submission": checkpoint_values.get(
                        "submission"
                    ),
                    "draft_summary": checkpoint_values.get(
                        "draft_summary"
                    ),
                    "classification": checkpoint_values.get(
                        "classification"
                    ),
                    "idea_assessment": checkpoint_values.get(
                        "idea_assessment"
                    ),
                    "reviewer_feedback": checkpoint_values.get(
                        "reviewer_feedback"
                    ),
                    "details_available": True,
                })
            )

        except Exception:
            logger.exception(
                "Could not load approval details: "
                "task_id=%s thread_id=%s",
                task_id,
                thread_id,
            )
        finally:
            close_graph_context(context)
    return approvals

@reviewer_router.get("/pending")
def reviewer_pending(reviewer_id: str):
    return {
        "approvals": reviewer_approval_rows(
            reviewer_id,
            "pending",
        )
    }

@reviewer_router.get("/escalated")
def reviewer_escalated(reviewer_id: str):
    return {
        "approvals": reviewer_approval_rows(
            reviewer_id,
            "escalated",
        )
    }

# REVIEWER: APPROVE / REJECT / IMPROVE

@reviewer_router.post("/decision")
def reviewer_decision(
    request: DecisionRequest,
):
    reviewer_id = request.reviewer_id.strip()
    task_id = request.task_id.strip()
    action = request.action.strip().upper()
    comment = (request.comment or "").strip()

    validate_user(reviewer_id, "REVIEWER")

    if action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail="Action must be APPROVE, REJECT, or IMPROVE.",
        )

    if action == "IMPROVE" and not comment:
        raise HTTPException(
            status_code=422,
            detail="A comment is required when choosing IMPROVE.",
        )

    # Resolve the exact approval cycle selected by the reviewer.
    approval = fetch_one(
        """
        SELECT
            task_id,
            thread_id,
            status,
            escalated,
            action
        FROM dbo.Approvals
        WHERE task_id = ?
        """,
        (task_id,),
    )

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Task ID not found in Approvals.",
        )

    thread_id = str(approval["thread_id"])
    approval_status = str(
        approval["status"]
    ).upper()

    if approval_status not in {"PENDING", "ESCALATED"}:
        raise HTTPException(
            status_code=409,
            detail=(
                "This review has already been handled "
                "or is being processed."
            ),
        )

    run = fetch_one(
        """
        SELECT
            task_id,
            thread_id,
            user_id,
            status
        FROM dbo.Runs
        WHERE task_id = ?
          AND thread_id = ?
        """,
        (task_id, thread_id),
    )

    if run is None:
        raise HTTPException(
            status_code=409,
            detail="The review has no matching Runs record.",
        )

    graph, context = get_graph()
    config = graph_config(thread_id)
    claimed = False

    try:
        snapshot = graph.get_state(config)

        payload = get_interrupt_payload(
            snapshot,
            APPROVAL_INTERRUPT,
        )

        if payload is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The workflow is not waiting for reviewer "
                    "approval. Refresh the reviewer queue."
                ),
            )

        # Confirm that this checkpoint belongs to the same idea.
        checkpoint_values = dict(
            getattr(snapshot, "values", {}) or {}
        )

        checkpoint_thread_id = str(
            checkpoint_values.get("thread_id") or ""
        )

        if checkpoint_thread_id != thread_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The checkpoint does not match this workflow "
                    "thread. Refresh the reviewer queue."
                ),
            )

        # Confirm that the selected draft is the latest submitted one.
        latest_run = get_latest_run_for_thread(
            thread_id,
            str(run["user_id"]),
        )

        if (
            latest_run is None
            or str(latest_run["task_id"]) != task_id
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This is not the latest submitted draft "
                    "for this idea. Refresh the reviewer queue."
                ),
            )

        # Atomically claim the approval to prevent concurrent decisions.
        with db_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    UPDATE dbo.Approvals
                    SET status = 'PROCESSING',
                        reviewer_id = ?
                    WHERE task_id = ?
                      AND thread_id = ?
                      AND status IN ('PENDING', 'ESCALATED')
                    """,
                    (reviewer_id, task_id, thread_id),
                )

                if cursor.rowcount != 1:
                    conn.rollback()

                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Another reviewer has claimed "
                            "or handled this task."
                        ),
                    )

                conn.commit()
                claimed = True

            except HTTPException:
                raise

            except Exception:
                conn.rollback()
                raise

            finally:
                cursor.close()

        # Resume using the same thread checkpoint.
        # The task_id is not needed in the interrupt payload.
        try:
            graph.invoke(
                Command(
                    resume={
                        "action": action.lower(),
                        "comment": comment,
                    }
                ),
                config=config,
            )

            updated_snapshot = graph.get_state(config)

            result = update_run_from_snapshot(
                task_id,
                updated_snapshot,
            )

        except Exception as exc:
            logger.exception(
                "Graph resume failed for task_id=%s "
                "thread_id=%s",
                task_id,
                thread_id,
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "The decision was claimed but workflow "
                    "resumption could not be confirmed. Inspect "
                    "the checkpoint and approval row before retrying."
                ),
            ) from exc

        approval_result_status = {
            "APPROVE": "APPROVED",
            "REJECT": "REJECTED",
            "IMPROVE": "IMPROVE",
        }[action]

        affected = execute_sql(
            """
            UPDATE dbo.Approvals
            SET status = ?,
                responded_at = SYSUTCDATETIME(),
                reviewer_id = ?,
                action = ?,
                comment = ?
            WHERE task_id = ?
              AND thread_id = ?
              AND status = 'PROCESSING'
            """,
            (
                approval_result_status,
                reviewer_id,
                action,
                comment or None,
                task_id,
                thread_id,
            ),
        )

        if affected != 1:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The graph resumed, but the approval record "
                    "could not be finalized. Inspect this Task ID."
                ),
            )

        # Save an immutable reviewer decision history row.
        history_saved = True

        try:
            execute_sql(
                """
                INSERT INTO dbo.ReviewerDecisions
                    (
                        thread_id,
                        task_id,
                        reviewer_user_id,
                        action,
                        comment,
                        decided_at
                    )
                VALUES
                    (?, ?, ?, ?, ?, SYSUTCDATETIME())
                """,
                (
                    thread_id,
                    task_id,
                    reviewer_id,
                    action,
                    comment or None,
                ),
            )

        except Exception:
            history_saved = False

            logger.exception(
                "Decision applied but history insert failed: "
                "task_id=%s",
                task_id,
            )

        return json_safe({
            "task_id": task_id,
            "thread_id": thread_id,
            "message": (
                f"Decision {action} recorded."
                if history_saved
                else (
                    f"Decision {action} applied, but "
                    "decision history failed."
                )
            ),
            "decision_history_saved": history_saved,
            "decision": action,
            "approval_status": approval_result_status,
            "status": result["status"],
            "reviewer_feedback": result.get(
                "reviewer_feedback"
            ),
            "needs_draft_summary": result[
                "needs_draft_summary"
            ],
            "needs_approval": result["needs_approval"],
            "is_complete": result["is_complete"],
        })

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Reviewer decision failed: task_id=%s",
            task_id,
        )

        if claimed:
            logger.error(
                "Approval remains PROCESSING; inspect before "
                "retrying: task_id=%s",
                task_id,
            )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not process the reviewer decision. "
                "Check server logs."
            ),
        ) from exc

    finally:
        close_graph_context(context)