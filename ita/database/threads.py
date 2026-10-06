import pyodbc
from database.connection import DB_URI

def create_thread(user_name: str, thread_id: str):
    """
    Create a new thread for a user.

    New threads start as IN_PROGRESS.
    """

    conn = pyodbc.connect(DB_URI)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO UserThreads
            (
                user_name,
                thread_id,
                status
            )
            VALUES (?, ?, 'IN_PROGRESS')
            """,
            user_name,
            thread_id
        )

        conn.commit()

    finally:
        conn.close()


def get_active_thread(user_name: str):
    """
    Return the user's latest IN_PROGRESS thread.

    Returns None if the user has no unfinished workflow.
    """

    conn = pyodbc.connect(DB_URI)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT TOP 1 thread_id
            FROM UserThreads
            WHERE user_name = ?
              AND status = 'IN_PROGRESS'
            ORDER BY created_at DESC
            """,
            user_name
        )

        row = cursor.fetchone()

        if row:
            return row[0]

        return None

    finally:
        conn.close()


def mark_thread_completed(thread_id: str):
    """
    Mark a thread as completed.
    """

    conn = pyodbc.connect(DB_URI)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE UserThreads
            SET
                status = 'COMPLETED',
                completed_at = SYSUTCDATETIME()
            WHERE thread_id = ?
              AND status = 'IN_PROGRESS'
            """,
            thread_id
        )

        conn.commit()

    finally:
        conn.close()


def get_user_threads(user_name: str):
    """
    Return all threads belonging to a user.
    """

    conn = pyodbc.connect(DB_URI)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                thread_id,
                status,
                created_at,
                completed_at
            FROM UserThreads
            WHERE user_name = ?
            ORDER BY created_at DESC
            """,
            user_name
        )

        return cursor.fetchall()

    finally:
        conn.close()