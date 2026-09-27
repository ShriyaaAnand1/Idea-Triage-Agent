from difflib import SequenceMatcher

from graph.state import AgentGraph

from utils.node_utils import (
    utc_now,
    start_timer,
    duration_ms,
    add_node_history,
)

from logger.logging import logger


IDEAS_FILE = "data/ideas.txt"

SIMILARITY_THRESHOLD = 0.80
TOP_K = 3


def normalize_text(text: str) -> str:
    return " ".join(
        text.lower().split()
    )


def calculate_similarity(
    new_idea: str,
    existing_idea: str,
) -> float:

    return round(
        SequenceMatcher(
            None,
            normalize_text(new_idea),
            normalize_text(existing_idea),
        ).ratio(),
        2,
    )


def load_existing_ideas() -> list[str]:

    try:

        with open(
            IDEAS_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            content = file.read()

    except FileNotFoundError:

        raise FileNotFoundError(
            f"Ideas file not found: {IDEAS_FILE}"
        )

    ideas = [
        idea.strip()
        for idea in content.split("\n\n")
        if idea.strip()
    ]

    return ideas


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

        submission = state.get("submission")

        if not submission:
            raise ValueError(
                "Submission is required for duplicate check"
            )

        existing_ideas = load_existing_ideas()

        if not existing_ideas:

            print(
                "\nNo existing ideas found."
            )

            next_node = "Draft Summary"

            node_output = {
                "duplicate_found": False,
                "duplicate_matches": [],
                "current_node": node_name,
                "status": "DUPLICATE_CHECKED",
            }

        else:

            matches = []

            for idea in existing_ideas:

                similarity = calculate_similarity(
                    submission,
                    idea,
                )

                matches.append(
                    {
                        "submission": idea,
                        "similarity": similarity,
                    }
                )

            matches.sort(
                key=lambda match: match["similarity"],
                reverse=True,
            )

            top_matches = matches[:TOP_K]

            duplicate_found = (
                top_matches[0]["similarity"]
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
                "duplicate_matches": top_matches,
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
                    "duration_ms": round(elapsed, 2),
                    "success": True,
                    "previous_node": previous_node,
                    "next_node": next_node,
                    "duplicate_found": node_output[
                        "duplicate_found"
                    ],
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