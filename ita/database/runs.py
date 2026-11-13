import uuid
from typing import Optional

from database.connection import db_connection
from database.queries import fetch_one, execute_sql

def create_run(
    thread_id,
    user_id=None,
    status="IN_PROGRESS",
    current_node="Submission",
    started_at=None,
):
    """Insert a new workflow run."""
    if not thread_id:
        raise ValueError("thread_id cannot be empty")

    query = """
        INSERT INTO dbo.Runs
        (
            thread_id,
            status,
            current_node,
            started_at,
            completed_at,
            user_id
        )
        VALUES
        (
            ?, ?, ?,
            COALESCE(?, SYSUTCDATETIME()),
            NULL,
            ?
        )
    """

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            query,
            str(thread_id).strip(),
            status,
            current_node,
            started_at,
            user_id,
        )
        conn.commit()


def update_run_status(
    thread_id,
    status,
    current_node=None,
    completed=False,
):
    """Update a run without accidentally clearing its current node."""
    query = """
        UPDATE dbo.Runs
        SET
            status = ?,
            current_node = COALESCE(?, current_node),
            completed_at = CASE
                WHEN ? = 1 THEN SYSUTCDATETIME()
                ELSE completed_at
            END
        where thread_id = ?
    """

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            query,
            status,
            current_node,
            completed,
            str(thread_id).strip(),
        )
        updated = cursor.rowcount 
        conn.commit() 
        return updated > 0


def get_runs_by_user(user_id):
    """Retrieve all workflow runs belonging to a user."""
    query = """
        SELECT
            thread_id,
            status,
            current_node,
            started_at,
            completed_at,
            user_id
        FROM dbo.Runs
        WHERE user_id = ?
        ORDER BY started_at DESC
    """

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, user_id)

        return [
            {
                "thread_id": row[0],
                "status": row[1],
                "current_node": row[2],
                "started_at": row[3],
                "completed_at": row[4],
                "user_id": row[5],
            }
            for row in cursor.fetchall()
        ]
    

#main
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