import pyodbc

from database.connection import DB_URI


def create_user(user_name: str, thread_id: str):
    """
    Store a new user and their thread ID.
    """

    conn = pyodbc.connect(DB_URI)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO Users (user_name, thread_id)
            VALUES (?, ?)
            """,
            user_name,
            thread_id
        )

        conn.commit()

    finally:
        conn.close()


def get_thread_id(user_name: str):
    """
    Retrieve the thread ID associated with a user.
    Returns None if the user does not exist.
    """

    conn = pyodbc.connect(DB_URI)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT thread_id
            FROM Users
            WHERE user_name = ?
            """,
            user_name
        )

        row = cursor.fetchone()

        if row:
            return row[0]

        return None

    finally:
        conn.close()