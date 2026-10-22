
from database.connection import db_connection
from fastapi import HTTPException
from database.queries import fetch_one

VALID_ROLES = {"USER", "REVIEWER"}


def get_permitted_users(role=None):
    """
    Return active permitted users.
    If role is supplied, filter by USER or REVIEWER.
    """
    if role is not None:
        role = role.upper()

        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")

    query = """
        SELECT user_id, role, is_active, created_at
        FROM dbo.PermittedUsers
        WHERE is_active = 1
    """

    params = ()

    if role is not None:
        query += " AND role = ?"
        params = (role,)

    query += " ORDER BY user_id"

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)

        return [
            {
                "user_id": row[0],
                "role": row[1],
                "is_active": bool(row[2]),
                "created_at": row[3],
            }
            for row in cursor.fetchall()
        ]


def validate_permitted_user(user_id, role=None):
    """Check whether a user exists, is active, and has the required role."""
    if role is not None:
        role = role.upper()

        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")

    query = """
        SELECT 1
        FROM dbo.PermittedUsers
        WHERE user_id = ?
          AND is_active = 1
    """

    params = [user_id]

    if role is not None:
        query += " AND role = ?"
        params.append(role)

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, *params)
        return cursor.fetchone() is not None
    
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