
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langgraph.types import Command

from database.connection import db_connection, get_checkpointer
from database.approvals import escalate_expired_approvals
from graph.workflow import create_graph


logger = logging.getLogger(__name__)

APPROVAL_TIMEOUT_MINUTES = 2
ESCALATION_CHECK_SECONDS = 10

DRAFT_INTERRUPT = "draft_summary_required"
APPROVAL_INTERRUPT = "approval_required"

VALID_ACTIONS = {"APPROVE", "REJECT", "IMPROVE"}


# DATABASE HELPERS

def fetch_one(sql: str, params: tuple = ()) -> Optional[dict]:
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            row = cursor.fetchone()

            if row is None:
                return None

            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, row))
        finally:
            cursor.close()


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            columns = [column[0] for column in cursor.description]

            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        finally:
            cursor.close()


def execute_sql(sql: str, params: tuple = ()) -> int:
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            affected = cursor.rowcount
            conn.commit()
            return affected
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(value, default=str, ensure_ascii=False)
    )


def ensure_ideas_table() -> None:
    execute_sql(
        """
        IF OBJECT_ID('dbo.Ideas', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.Ideas (
                thread_id NVARCHAR(255) NOT NULL PRIMARY KEY,
                user_id NVARCHAR(255) NOT NULL,
                submission NVARCHAR(MAX) NOT NULL,
                status NVARCHAR(50) NOT NULL,
                created_at DATETIME2 NOT NULL
                    CONSTRAINT DF_Ideas_created_at
                    DEFAULT SYSUTCDATETIME()
            );
        END;
        """
    )


# USER / REVIEWER VALIDATION

def validate_user(user_id: str, expected_role: str) -> None:
    row = fetch_one(
        """
        SELECT user_id
        FROM dbo.PermittedUsers
        WHERE user_id = ?
          AND role = ?
          AND is_active = 1
        """,
        (user_id.strip(), expected_role.upper()),
    )

    if row is None:
        raise HTTPException(
            status_code=403,
            detail=f"Invalid or inactive {expected_role.lower()} ID.",
        )


# LANGGRAPH HELPERS

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


# DRAFT / RUN HELPERS

def get_latest_run_for_thread(
    thread_id: str,
    user_id: str,
) -> Optional[dict]:
    """
    Return the latest submitted draft for an idea.

    task_id identifies a draft cycle.
    thread_id identifies the entire idea workflow.
    """
    return fetch_one(
        """
        SELECT TOP 1
            task_id,
            thread_id,
            user_id,
            status,
            current_node,
            started_at,
            completed_at
        FROM dbo.Runs
        WHERE thread_id = ?
          AND user_id = ?
        ORDER BY started_at DESC, task_id DESC
        """,
        (thread_id, user_id),
    )


def get_latest_run_for_thread_any_user(
    thread_id: str,
) -> Optional[dict]:
    return fetch_one(
        """
        SELECT TOP 1
            task_id,
            thread_id,
            user_id,
            status,
            current_node,
            started_at,
            completed_at
        FROM dbo.Runs
        WHERE thread_id = ?
        ORDER BY started_at DESC, task_id DESC
        """,
        (thread_id,),
    )


def insert_run(
    task_id: str,
    thread_id: str,
    user_id: str,
) -> None:
    """
    Insert one Run for one draft submission.

    This ID is stored in SQL, not required in checkpoint state.
    """
    execute_sql(
        """
        INSERT INTO dbo.Runs
            (
                task_id,
                thread_id,
                status,
                current_node,
                started_at,
                completed_at,
                user_id
            )
        VALUES
            (?, ?, 'SUBMITTED', 'Draft Summary',
             SYSUTCDATETIME(), NULL, ?)
        """,
        (task_id, thread_id, user_id),
    )


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


# IDEA LOOKUP HELPERS

def get_owned_idea_by_thread(
    thread_id: str,
    user_id: str,
) -> dict:
    row = fetch_one(
        """
        SELECT
            thread_id,
            user_id,
            submission,
            status,
            created_at
        FROM dbo.Ideas
        WHERE thread_id = ?
          AND user_id = ?
        """,
        (thread_id, user_id),
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Idea not found for this user.",
        )

    return row


def get_owned_idea_by_task(
    task_id: str,
    user_id: str,
) -> dict:
    """
    Resolve any historical draft Task ID to its permanent thread.
    """
    row = fetch_one(
        """
        SELECT
            r.task_id,
            r.thread_id,
            r.user_id,
            r.status
        FROM dbo.Runs AS r
        INNER JOIN dbo.Ideas AS i
            ON i.thread_id = r.thread_id
        WHERE r.task_id = ?
          AND r.user_id = ?
          AND i.user_id = ?
        """,
        (task_id, user_id, user_id),
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Task ID not found for this user.",
        )

    return row


# REQUEST MODELS

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


# APPLICATION LIFECYCLE / ESCALATION

async def escalation_loop():
    logger.info("Approval escalation loop started")

    while True:
        try:
            count = await asyncio.to_thread(
                escalate_expired_approvals
            )

            if count:
                logger.warning(
                    "Escalated %s approval(s)",
                    count,
                )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Approval escalation check failed"
            )

        await asyncio.sleep(ESCALATION_CHECK_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_ideas_table()

    context = get_checkpointer()
    checkpointer = context.__enter__()

    escalation_task = None

    try:
        checkpointer.setup()

        escalation_task = asyncio.create_task(
            escalation_loop()
        )

        yield

    finally:
        if escalation_task:
            escalation_task.cancel()

            try:
                await escalation_task
            except asyncio.CancelledError:
                pass

        context.__exit__(None, None, None)


app = FastAPI(
    title="Idea Triage Agent API",
    version="2.2.0",
    lifespan=lifespan,
)


@app.get("/")
def home():
    return {
        "message": "Idea Triage Agent API is running",
        "status": "healthy",
    }


# USER: SUBMIT IDEA

@app.post("/user/ideas")
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


# USER: SUBMIT FIRST DRAFT OR REVISED DRAFT

@app.post("/user/draft-summary")
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
            "Draft submission failed: thread_id=%s task_id=%s",
            thread_id,
            supplied_task_id,
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


# USER: LIST IDEAS

@app.get("/user/{user_id}/ideas")
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

@app.get("/user/ideas/{task_id}")
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


# REVIEWER: PENDING / ESCALATED QUEUES

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


@app.get("/reviewer/pending")
def reviewer_pending(reviewer_id: str):
    return {
        "approvals": reviewer_approval_rows(
            reviewer_id,
            "pending",
        )
    }


@app.get("/reviewer/escalated")
def reviewer_escalated(reviewer_id: str):
    return {
        "approvals": reviewer_approval_rows(
            reviewer_id,
            "escalated",
        )
    }


# REVIEWER: APPROVE / REJECT / IMPROVE

@app.post("/reviewer/decision")
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
