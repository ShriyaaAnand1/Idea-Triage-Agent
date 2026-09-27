from langgraph.types import interrupt

from graph.state import AgentGraph

from utils.node_utils import (
    utc_now,
    start_timer,
    duration_ms,
    add_node_history,
)

from logger.logging import logger


def human_approval_node(
    state: AgentGraph,
) -> dict:

    node_name = "Human Approval"

    started_at = utc_now()
    timer = start_timer()

    previous_node = state.get("current_node")

    node_input = {
        "draft_available": bool(
            state.get("draft_summary")
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

        # Start measuring human decision time
        decision_timer = start_timer()

        decision = interrupt(
            {
                "message": (
                    "Do you want to approve the idea, "
                    "reject the idea, or request improvements?"
                ),
                "options": [
                    "approve",
                    "reject",
                    "improve",
                ],
            }
        )

        decision_time = duration_ms(
            decision_timer
        )

        action = decision.get("action")

        comment = decision.get(
            "comment",
            "",
        )

        if action not in {
            "approve",
            "reject",
            "improve",
        }:

            raise ValueError(
                f"Invalid human decision: {action}"
            )

        if action == "approve":
            next_node = "Finalize"

        elif action == "reject":
            next_node = "END"

        else:
            next_node = "Enrich"

        node_output = {
            "current_decision": {
                "action": action,
                "comment": comment,
            },

            "reviewer_feedback": comment,

            "current_node": node_name,

            "status": "HUMAN_DECISION",
        }

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
            "Human decision recorded",
            extra={
                "extra_fields": {
                    "event": "human_decision",
                    "node": node_name,
                    "decision": action,
                    "decision_time_ms": round(
                        decision_time,
                        2,
                    ),
                    "next_node": next_node,
                }
            }
        )

        logger.info(
            "Node completed",
            extra={
                "extra_fields": {
                    "event": "node_end",
                    "node": node_name,
                    "duration_ms": round(
                        elapsed,
                        2,
                    ),
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
                    "duration_ms": round(
                        elapsed,
                        2,
                    ),
                    "success": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            }
        )

        raise