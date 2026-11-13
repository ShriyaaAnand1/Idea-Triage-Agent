import uuid
from database.connection import db_connection

VALID_ACTIONS = {"APPROVE", "REJECT", "IMPROVE"}


def _uuid_text(value, field_name):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(
            f"{field_name} must be a valid UUID: {value}"
        ) from exc


def create_reviewer_decision(
    thread_id,
    task_id,
    reviewer_user_id,
    action,
    comment="",
):
    """ 
    Record a reviewer decision. Update Approvals and insert ReviewerDecisions in the same transaction. 
    """ 
    if not thread_id or not str(thread_id).strip(): 
        raise ValueError("thread_id cannot be empty") 
    if not task_id or not str(task_id).strip():
        raise ValueError("task_id cannot be empty") 
    if not reviewer_user_id or not str(reviewer_user_id).strip(): 
        raise ValueError("reviewer_user_id cannot be empty") 
    thread_id = str(thread_id).strip() 
    task_id = str(task_id).strip() 
    reviewer_user_id = str(reviewer_user_id).strip() 
    action = action.strip().upper() 
    comment = comment or ""

    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid reviewer action: {action}")

    if action == "IMPROVE" and not comment.strip():
        raise ValueError(
            "A non-empty comment is required for IMPROVE."
        )

    status_by_action = {
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "IMPROVE": "IMPROVE",
    }

    new_status = status_by_action[action]

    with db_connection() as conn:
        cursor = conn.cursor()

        # Validate the reviewer.
        cursor.execute(
            """
            SELECT 1
            FROM dbo.PermittedUsers
            WHERE user_id = ?
              AND role = 'REVIEWER'
              AND is_active = 1
            """,
            reviewer_user_id,
        )

        if cursor.fetchone() is None:
            raise ValueError(
                "Reviewer does not exist, is inactive, "
                "or does not have the REVIEWER role."
            )

        # Lock the approval while processing this decision.
        cursor.execute(
            """
            SELECT thread_id, status
            FROM dbo.Approvals WITH (UPDLOCK, ROWLOCK)
            WHERE task_id = ?
            """,
            task_id,
        )

        approval = cursor.fetchone()

        if approval is None:
            raise ValueError(
                f"No approval found for task_id: {task_id}"
            )

        stored_thread_id = approval[0].strip()
        stored_status = approval[1]

        if stored_thread_id.casefold() != thread_id.casefold():
            raise ValueError(
                f"Approval has already been answered. " 
                f"Current status: {stored_status}"
            )

        if stored_status not in {"PENDING", "ESCALATED"}:
            raise ValueError(
                f"Approval has already been answered. "
                f"Current status: {stored_status}"
            )

        # Update the original approval record.
        cursor.execute(
            """
            UPDATE dbo.Approvals
            SET
                status = ?,
                responded_at = SYSUTCDATETIME(),
                reviewer_id = ?,
                action = ?,
                comment = ?
            WHERE task_id = ?
              AND thread_id = ?
              AND status IN ('PENDING', 'ESCALATED')
            """,
            new_status,
            reviewer_user_id,
            action,
            comment,
            task_id,
            thread_id
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "The approval was already processed."
            )

        # Save the permanent reviewer-decision record.
        cursor.execute(
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
            VALUES (?, ?, ?, ?, ?,SYSUTCDATETIME())
            """,
            thread_id,
            task_id,
            reviewer_user_id,
            action,
            comment,
        )
        conn.commit()

    return {
        "thread_id": thread_id,
        "task_id": task_id,
        "reviewer_user_id": reviewer_user_id,
        "action": action,
        "status": new_status,
        "comment": comment,
    }