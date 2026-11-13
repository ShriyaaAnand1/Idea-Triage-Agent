
import json
import uuid

from database.connection import db_connection


def _uuid_text(value, field_name):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(
            f"{field_name} must be a valid UUID: {value}"
        ) from exc


def _to_json(value):
    if value is None:
        return None

    return json.dumps(
        value,
        default=str,
        ensure_ascii=False,
    )


def create_run_history(
    thread_id,
    node_name,
    started_at,
    completed_at=None,
    duration_ms=None,
    success=True,
    input_state=None,
    output_state=None,
    previous_node=None,
    next_node=None,
    error_type=None,
    error_message=None,
):
    if not thread_id or not str(thread_id).strip(): 
        raise ValueError("thread_id cannot be empty")

    if duration_ms is not None:
        duration_ms = float(duration_ms)

    query = """
        INSERT INTO dbo.RunHistory
        (
            thread_id,
            node_name,
            started_at,
            completed_at,
            duration_ms,
            success,
            input_state,
            output_state,
            previous_node,
            next_node,
            error_type,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            query,
            str(thread_id).strip(),
            node_name,
            started_at,
            completed_at,
            duration_ms,
            bool(success),
            _to_json(input_state),
            _to_json(output_state),
            previous_node,
            next_node,
            error_type,
            error_message,
        )
        conn.commit()

def get_run_history(thread_id): 
    """Return node execution history for one workflow.""" 
    query = """ 
    SELECT 
      thread_id, 
      node_name, 
      started_at,
      completed_at, 
      duration_ms, 
      success, 
      input_state, 
      output_state, 
      previous_node, 
      next_node, 
      error_type, 
      error_message 
      FROM dbo.RunHistory 
      WHERE thread_id = ? 
      ORDER BY started_at 
      """
    with db_connection() as conn: 
        cursor = conn.cursor() 
        cursor.execute(query, str(thread_id).strip()) 
        columns = [ column[0] for column in cursor.description ] 
        return [ dict(zip(columns, row)) for row in cursor.fetchall() ]

