
import uuid
from services.workflow_service import get_graph,graph_config,close_graph_context,get_interrupt_payload,json_safe,update_run_from_snapshot
from database.queries import execute_sql,fetch_all,fetch_one,get_owned_idea_by_task
from database.users import validate_user
from database.runs import get_latest_run_for_thread
from fastapi import APIRouter, HTTPException
from routes.schema import IdeaRequest,DraftSummaryRequest
from logger.logging import logger
from langgraph.types import Command
from database.runs import insert_run
from database.queries import get_owned_idea_by_thread

DRAFT_INTERRUPT = "draft_summary_required"

user_router=APIRouter(prefix="/user",tags=["User"])


@user_router.post("/ideas")
def submit_idea(request: IdeaRequest):
    user_id = request.user_id.strip()
    idea_text = request.idea.strip()

    validate_user(user_id, "USER")

    thread_id = str(uuid.uuid4())

    execute_sql(
        """
        INSERT INTO dbo.Ideas
            (
                thread_id,
                user_id,
                submission,
                status,
                created_at
            )
        VALUES
            (?, ?, ?, 'SUBMITTED', SYSUTCDATETIME())
        """,
        (thread_id, user_id, idea_text),
    )

    initial_state = {
        "user_id": user_id,
        "thread_id": thread_id,
        "submission": idea_text,
        "current_node": "Submission",
        "status": "SUBMITTED",
        "draft_summary": None,
        "draft_versions": [],
        "decision_history": [],
        "revision_count": 0,
        "node_history": [],
        "reviewer_feedback": None,
        "reviewer_decision": None,
    }

    graph, context = get_graph()
    config = graph_config(thread_id)

    try:
        graph.invoke(initial_state, config=config)

        snapshot = graph.get_state(config)

        # No Run or draft Task ID exists before the first draft.
        result = update_run_from_snapshot(None, snapshot)

        result["task_id"] = None
        result["thread_id"] = thread_id
        result["message"] = (
            "Idea submitted. Please provide a draft summary."
        )

        return json_safe(result)

    except Exception as exc:
        logger.exception(
            "Could not process thread_id=%s",
            thread_id,
        )

        execute_sql(
            """
            UPDATE dbo.Ideas
            SET status = 'ERROR'
            WHERE thread_id = ?
            """,
            (thread_id,),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not process the idea. "
                "Check the server logs."
            ),
        ) from exc

    finally:
        close_graph_context(context)

@user_router.get("/{user_id}/ideas")
def get_user_ideas(user_id: str):
    user_id = user_id.strip()

    validate_user(user_id, "USER")

    rows = fetch_all(
        """
        SELECT
            i.thread_id,
            i.user_id,
            i.submission,
            i.status AS idea_status,
            i.created_at,
            r.task_id,
            r.status AS run_status,
            r.current_node,
            r.started_at,
            r.completed_at
        FROM dbo.Ideas AS i
        OUTER APPLY (
            SELECT TOP 1
                task_id,
                status,
                current_node,
                started_at,
                completed_at
            FROM dbo.Runs
            WHERE thread_id = i.thread_id
            ORDER BY started_at DESC, task_id DESC
        ) AS r
        WHERE i.user_id = ?
        ORDER BY i.created_at DESC
        """,
        (user_id,),
    )

    ideas = []

    for row in rows:
        thread_id = str(row["thread_id"])

        task_id = (
            str(row["task_id"])
            if row["task_id"]
            else None
        )

        graph, context = get_graph()

        try:
            snapshot = graph.get_state(
                graph_config(thread_id)
            )

            # Use the latest Run's Task ID from SQL.
            item = update_run_from_snapshot(
                task_id,
                snapshot,
            )

            item["started_at"] = row["started_at"]
            item["completed_at"] = row["completed_at"]
            item["created_at"] = row["created_at"]
            item["checkpoint_available"] = True

        except Exception:
            logger.exception(
                "Could not load checkpoint for thread_id=%s",
                thread_id,
            )

            item = {
                "task_id": task_id,
                "thread_id": thread_id,
                "submission": row["submission"],
                "status": (
                    row["run_status"]
                    or row["idea_status"]
                ),
                "current_node": row["current_node"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "created_at": row["created_at"],
                "checkpoint_available": False,
            }

        finally:
            close_graph_context(context)

        ideas.append(json_safe(item))

    return {"ideas": ideas}


# USER: REOPEN IDEA BY TASK ID OR THREAD ID

@user_router.get("/ideas/{task_id}")
def get_user_idea(
    task_id: str,
    user_id: str,
):
    user_id = user_id.strip()
    lookup_id = task_id.strip()

    validate_user(user_id, "USER")

    # Before the first draft, users can reopen by thread_id.
    thread_row = fetch_one(
        """
        SELECT thread_id, user_id, submission
        FROM dbo.Ideas
        WHERE thread_id = ?
          AND user_id = ?
        """,
        (lookup_id, user_id),
    )

    if thread_row:
        thread_id = str(thread_row["thread_id"])

    else:
        # A historical draft Task ID resolves to its thread.
        run = get_owned_idea_by_task(
            lookup_id,
            user_id,
        )

        thread_id = str(run["thread_id"])

    # Always show the latest draft ID, not the ID used to open it.
    latest_run = get_latest_run_for_thread(
        thread_id,
        user_id,
    )

    fallback_task_id = (
        str(latest_run["task_id"])
        if latest_run and latest_run["task_id"]
        else None
    )

    graph, context = get_graph()

    try:
        snapshot = graph.get_state(
            graph_config(thread_id)
        )

        result = update_run_from_snapshot(
            fallback_task_id,
            snapshot,
        )

        result["thread_id"] = thread_id
        result["checkpoint_available"] = True

        return json_safe(result)

    except Exception as exc:
        logger.exception(
            "Could not load thread_id=%s",
            thread_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not load this idea's saved status.",
        ) from exc

    finally:
        close_graph_context(context)

@user_router.post("/draft-summary")
def submit_draft_summary(
    request: DraftSummaryRequest,
):
    user_id = request.user_id.strip()
    thread_id = request.thread_id.strip()

    supplied_task_id = (
        request.task_id.strip()
        if request.task_id and request.task_id.strip()
        else None
    )

    summary = request.draft_summary.strip()

    validate_user(user_id, "USER")

    if not summary:
        raise HTTPException(
            status_code=422,
            detail="Draft summary cannot be empty.",
        )

    get_owned_idea_by_thread(thread_id, user_id)

    graph, context = get_graph()
    config = graph_config(thread_id)

    try:
        snapshot = graph.get_state(config)

        payload = get_interrupt_payload(
            snapshot,
            DRAFT_INTERRUPT,
        )

        if payload is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This workflow is not waiting for a draft "
                    "summary. Refresh the idea status before retrying."
                ),
            )

        values = dict(
            getattr(snapshot, "values", {}) or {}
        )

        checkpoint_thread_id = str(
            values.get("thread_id") or ""
        )

        if checkpoint_thread_id != thread_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The thread ID does not match "
                    "the saved checkpoint."
                ),
            )

        # Determine the previous draft from SQL, not checkpoint state.
        previous_run = get_latest_run_for_thread(
            thread_id,
            user_id,
        )

        if previous_run is None:
            # First draft: no earlier Task ID should be supplied.
            if supplied_task_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This is the first draft. "
                        "Submit it without a Task ID."
                    ),
                )

            is_revision = False
            previous_task_id = None

        else:
            previous_task_id = str(
                previous_run["task_id"]
            )

            if supplied_task_id != previous_task_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"The current draft Task ID is "
                        f"{previous_task_id}. "
                        "Refresh the idea before submitting."
                    ),
                )

            previous_approval = fetch_one(
                """
                SELECT status, action
                FROM dbo.Approvals
                WHERE task_id = ?
                  AND thread_id = ?
                """,
                (previous_task_id, thread_id),
            )

            if previous_approval is None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The previous draft has no approval record."
                    ),
                )

            previous_status = str(
                previous_approval["status"] or ""
            ).upper()

            previous_action = str(
                previous_approval["action"] or ""
            ).upper()

            if (
                previous_status != "IMPROVE"
                or previous_action != "IMPROVE"
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "A revised draft can only be submitted "
                        "after the reviewer requests improvement."
                    ),
                )

            is_revision = True

        # Each submitted draft gets a new Task ID.
        current_task_id = str(uuid.uuid4())

        # Persist the draft cycle in SQL.
        insert_run(
            current_task_id,
            thread_id,
            user_id,
        )

        # Do not write task_id into the checkpoint.
        # Resume the existing draft-summary interrupt.
        graph.invoke(
            Command(resume=summary),
            config=config,
        )

        updated_snapshot = graph.get_state(config)

        # Update only the Run belonging to this submission.
        result = update_run_from_snapshot(
            current_task_id,
            updated_snapshot,
        )

        updated_values = dict(
            getattr(updated_snapshot, "values", {}) or {}
        )

        if is_revision and previous_task_id:
            execute_sql(
                """
                UPDATE dbo.Runs
                SET status = 'IMPROVED',
                    completed_at = COALESCE(
                        completed_at,
                        SYSUTCDATETIME()
                    )
                WHERE task_id = ?
                  AND thread_id = ?
                """,
                (previous_task_id, thread_id),
            )

        result["task_id"] = current_task_id
        result["thread_id"] = thread_id

        result["draft_summary"] = (
            updated_values.get("draft_summary")
            or summary
        )

        result["message"] = (
            "Revised draft submitted successfully."
            if is_revision
            else "Draft summary submitted successfully."
        )

        return json_safe(result)

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
        "Draft submission failed: "
        "thread_id=%s task_id=%s error_type=%s error=%s",
        thread_id,
        supplied_task_id,
        type(exc).__name__,
        str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not submit the draft summary. "
                "Check the server logs."
            ),
        ) from exc

    finally:
        close_graph_context(context)