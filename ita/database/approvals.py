import uuid

from database.connection import db_connection


ESCALATION_TIMEOUT_MINUTES = 2


def _uuid_text(value, field_name="task_id"):
    """Validate a UUID and return its canonical string representation."""

    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(
            f"{field_name} must be a valid UUID."
        ) from exc


def _fetchone(cursor):
    row = cursor.fetchone()

    if row is None:
        return None

    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def _fetchall(cursor):
    columns = [column[0] for column in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]



def create_approval(thread_id: str, task_id: str) -> None:
    """
    Create one approval request per task cycle.

    Repeated execution of the Human Approval node must not create
    duplicate approvals for the same task_id/thread_id pair.
    """

    with db_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT task_id, thread_id
                FROM dbo.Approvals
                WHERE task_id = ? AND thread_id = ?
                """,
                (task_id, thread_id),
            )

            existing = cursor.fetchone()

            if existing is not None:
                return

            cursor.execute(
                """
                INSERT INTO dbo.Approvals
                    (thread_id, task_id, requested_at, responded_at,
                     status, reviewer_id, action, comment,
                     escalated, escalated_at)
                VALUES
                    (?, ?, SYSUTCDATETIME(), NULL,
                     'PENDING', NULL, NULL, NULL, 0, NULL)
                """,
                (thread_id, task_id),
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()

def get_approval(task_id):
    task_id = _uuid_text(task_id)

    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                thread_id,
                task_id,
                requested_at,
                responded_at,
                status,
                reviewer_id,
                action,
                comment,
                escalated,
                escalated_at
            FROM dbo.Approvals
            WHERE task_id = ?
            """,
            (task_id,),
        )

        return _fetchone(cursor)


def get_pending_approvals():
    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                thread_id,
                task_id,
                requested_at,
                status,
                reviewer_id,
                action,
                escalated,
                escalated_at
            FROM dbo.Approvals
            WHERE status = 'PENDING'
            ORDER BY requested_at ASC
            """
        )

        return _fetchall(cursor)


def get_escalated_approvals():
    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                thread_id,
                task_id,
                requested_at,
                status,
                reviewer_id,
                action,
                escalated,
                escalated_at
            FROM dbo.Approvals
            WHERE status = 'ESCALATED'
            ORDER BY requested_at ASC
            """
        )

        return _fetchall(cursor)


def escalate_expired_approvals():
    """
    Escalate pending approvals older than the configured timeout.

    Escalation changes the SQL status. It does not resume the graph.
    The reviewer can still respond to an escalated approval.
    """

    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE dbo.Approvals
            SET
                status = 'ESCALATED',
                escalated = 1,
                escalated_at = SYSUTCDATETIME()
            OUTPUT inserted.task_id
            WHERE
                status = 'PENDING'
                AND requested_at <= DATEADD(
                    MINUTE,
                    -?,
                    SYSUTCDATETIME()
                )
            """,
            (ESCALATION_TIMEOUT_MINUTES,),
        )

        rows = cursor.fetchall()
        conn.commit()

        return [str(row[0]) for row in rows]