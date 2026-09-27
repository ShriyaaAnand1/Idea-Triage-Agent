from graph.state import AgentGraph

from utils.node_utils import (
    utc_now,
    start_timer,
    duration_ms,
    add_node_history,
)

from logger.logging import logger


def draft_summary_node(
    state: AgentGraph,
) -> dict:

    node_name = "Draft Summary"

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

        print(
            "\n========== DRAFT SUMMARY =========="
        )

        print(
            "\nEnter the summary of the idea:"
        )

        draft = input("> ").strip()

        if not draft:
            raise ValueError(
                "Draft summary cannot be empty"
            )

        print(
            "\nDraft summary received."
        )

        print(
            "===================================\n"
        )

        node_output = {
            "draft_summary": draft,
            "current_node": node_name,
            "status": "DRAFT_CREATED",
        }

        next_node = "Human Approval"

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