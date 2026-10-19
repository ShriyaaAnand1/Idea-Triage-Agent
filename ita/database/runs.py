
import uuid

from database.connection import db_connection


def _uuid_text(value, field_name):
    """Validate and normalize a UUID for SQL Server."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(
            f"{field_name} must be a valid UUID: {value}"
        ) from exc


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