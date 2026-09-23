import time
import uuid

from graph.state import AgentGraph
from utils.node_utils import (
    utc_now,
    add_node_history,
)
from logger.logging import logger

def submission_node(state: AgentGraph) -> dict:

    node_name = "Submission"

    started_at = utc_now()
    start_time = time.perf_counter()

    # Run information
    run_id = state.get(
        "run_id"
    ) or str(uuid.uuid4())

    thread_id = state.get(
        "thread_id"
    ) or str(uuid.uuid4())

    correlation_id = state.get(
        "correlation_id"
    ) or str(uuid.uuid4())

    previous_node = state.get(
        "current_node"
    )

    # Safe input information
    node_input = {
        "submission_received": bool(
            state.get("submission")
        )
    }

    # Log node entry
    logger.info(
        "Node started",
        extra={
            "extra_fields": {
                "event": "node_start",
                "run_id": run_id,
                "correlation_id": correlation_id,
                "node": node_name,
            }
        }
    )

    try:

        # Node logic
        output = {
            "run_id": run_id,
            "thread_id": thread_id,
            "correlation_id": correlation_id,
            "current_node": node_name,
            "status": "STARTED",
            "revision_count": 0,
            "decision_history": [],
            "draft_versions": [],
            "node_history": [],
        }

        # Timing
        finished_at = utc_now()

        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        # Node history
        history = add_node_history(
            state=state,
            node_name=node_name,
            run_id=run_id,
            correlation_id=correlation_id,

            node_input=node_input,
            node_output=output,

            started_at=started_at,
            finished_at=finished_at,
            duration=duration_ms,

            success=True,

            previous_node=previous_node,
            next_node="Classify",
        )

        output["node_history"] = history

        # Log node exit
        logger.info(
            "Node completed",
            extra={
                "extra_fields": {
                    "event": "node_end",
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                    "node": node_name,
                    "duration_ms": round(
                        duration_ms,
                        2
                    ),
                    "success": True,
                    "next_node": "Classify",
                }
            }
        )

        return output

    except Exception as exc:

        finished_at = utc_now()

        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.error(
            "Node failed",
            extra={
                "extra_fields": {
                    "event": "node_error",
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                    "node": node_name,
                    "duration_ms": round(
                        duration_ms,
                        2
                    ),
                    "success": False,
                    "error_type": type(
                        exc
                    ).__name__,
                    "error_message": str(exc),
                }
            }
        )

        raise