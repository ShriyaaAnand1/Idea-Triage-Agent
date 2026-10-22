from typing import Any, Optional
from database.connection import db_connection
from fastapi import HTTPException

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