from graph.state import AgentGraph

from vectorstore.load_vs import (
    load_vectorstore
)

from utils.node_utils import (
    utc_now,
    start_timer,
    duration_ms,
    add_node_history,
)

from logger.logging import logger


SIMILARITY_THRESHOLD = 0.80
TOP_K = 3


vectorstore = load_vectorstore()


def duplicate_check_node(
    state: AgentGraph,
) -> dict:

    node_name = "Duplicate Check"

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

        submission = state.get(
            "submission"
        )

        if not submission:
            raise ValueError(
                "Submission is required for duplicate check"
            )

        results = (
            vectorstore.similarity_search_with_score(
                submission,
                k=TOP_K
            )
        )

        matches = []

        for document, distance in results:

            similarity = float(
                round(
                    1 - float(distance),
                    2
                )
            )

            matches.append(
                {
                    "submission": document.page_content,
                    "similarity": similarity,
                }
            )

        duplicate_found = False

        if matches:

            duplicate_found = bool(
                matches[0]["similarity"]
                >= SIMILARITY_THRESHOLD
            )

        print(
            "\n========== DUPLICATE CHECK =========="
        )

        print(
            f"Duplicate: "
            f"{'YES' if duplicate_found else 'NO'}"
        )

        print(
            "=====================================\n"
        )

        next_node = (
            "END"
            if duplicate_found
            else "Draft Summary"
        )

        node_output = {
            "duplicate_found": duplicate_found,

            "duplicate_matches": matches,

            "current_node": node_name,

            "status": (
                "DUPLICATE_FOUND"
                if duplicate_found
                else "DUPLICATE_CHECKED"
            ),
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
            "Node completed",
            extra={
                "extra_fields": {
                    "event": "node_end",
                    "node": node_name,
                    "duration_ms": round(
                        elapsed,
                        2
                    ),
                    "success": True,
                    "previous_node": previous_node,
                    "next_node": next_node,
                    "duplicate_found": duplicate_found,
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
                        2
                    ),
                    "success": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            }
        )

        raise