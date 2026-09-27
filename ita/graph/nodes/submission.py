from graph.state import AgentGraph

from utils.node_utils import (
    utc_now,
    start_timer,
    duration_ms,
    add_node_history,
)

from logger.logging import logger


def submission_node(state: AgentGraph) -> dict:

    node_name = "Submission"

    started_at = utc_now()
    timer = start_timer()

    previous_node = state.get("current_node")

    node_input = {
        "submission_received": bool(
            state.get("submission")
        )
    }

    logger.info(
        "Node started",
        extra={
            "extra_fields": {
                "event": "node_start",
                "node": node_name,
            }
        }
    )

    try:

        submission = state.get("submission")

        if not submission:
            raise ValueError(
                "Submission cannot be empty"
            )

        print("\n========== SUBMISSION ==========")

        print("\nIdea submitted:")
        print(submission)

        print("\n================================")

        node_output = {
            "current_node": node_name,
            "status": "SUBMITTED",
        }

        next_node = "Classify"

        finished_at = utc_now()
        elapsed = duration_ms(timer)

        history = add_node_history(
            state=state,
            node_name=node_name,
            node_input=node_input,
            node_output=node_output,
            started_at=started_at,
            finished_at=finished_at,
            duration=elapsed,
            success=True,
            previous_node=previous_node,
            next_node=next_node,
        )

        logger.info(
            "Node completed",
            extra={
                "extra_fields": {
                    "event": "node_end",
                    "node": node_name,
                    "duration_ms": round(elapsed, 2),
                    "success": True,
                    "previous_node": previous_node,
                    "next_node": next_node,
                }
            }
        )

        return {
            **node_output,
            "node_history": history,
        }

    except Exception as exc:

        elapsed = duration_ms(timer)

        logger.error(
            "Node failed",
            extra={
                "extra_fields": {
                    "event": "node_error",
                    "node": node_name,
                    "duration_ms": round(elapsed, 2),
                    "success": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            }
        )

        raise