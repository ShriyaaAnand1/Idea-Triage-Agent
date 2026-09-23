import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_timer():
    return time.perf_counter()


def duration_ms(start_time: float) -> float:
    return (time.perf_counter() - start_time) * 1000


def add_node_history(
    state,
    node_name: str,
    run_id: str,
    correlation_id: str,
    node_input: Dict[str, Any],
    node_output: Dict[str, Any],
    started_at: str,
    finished_at: str,
    duration: float,
    success: bool,
    previous_node: Optional[str],
    next_node: Optional[str],
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
):
    entry = {
        "node": node_name,
        "run_id": run_id,
        "correlation_id": correlation_id,
        "input": node_input,
        "output": node_output,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": round(duration, 2),
        "success": success,
        "error_type": error_type,
        "error_message": error_message,
        "previous_node": previous_node,
        "next_node": next_node,
    }

    history = state.get("node_history", [])

    return history + [entry]