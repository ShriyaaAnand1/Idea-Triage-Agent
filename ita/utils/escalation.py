import time
from datetime import datetime, timezone

import pyodbc

from database.connection import DB_URI


TIMEOUT_MINUTES = 2
CHECK_INTERVAL_SECONDS = 10


def check_escalations():

    conn = pyodbc.connect(DB_URI)

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                task_id,
                requested_at
            FROM Approvals
            WHERE status = 'PENDING'
              AND escalated = 0
            """
        )

        approvals = cursor.fetchall()

        now = datetime.now(timezone.utc)

        for approval in approvals:

            task_id = approval.task_id
            requested_at = approval.requested_at

            if requested_at.tzinfo is None:
                requested_at = requested_at.replace(
                    tzinfo=timezone.utc
                )

            elapsed_seconds = (
                now - requested_at
            ).total_seconds()

            if elapsed_seconds >= TIMEOUT_MINUTES * 60:

                cursor.execute(
                    """
                    UPDATE Approvals
                    SET
                        status = 'ESCALATED',
                        escalated = 1,
                        escalated_at = SYSUTCDATETIME()
                    WHERE task_id = ?
                      AND status = 'PENDING'
                      AND escalated = 0
                    """,
                    task_id,
                )

                print(
                    f"Approval {task_id} "
                    f"escalated after 2 minutes."
                )

        conn.commit()

    finally:
        conn.close()


if __name__ == "__main__":

    print("Escalation checker started.")

    while True:

        check_escalations()

        time.sleep(
            CHECK_INTERVAL_SECONDS
        )