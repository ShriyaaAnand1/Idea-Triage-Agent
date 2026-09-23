import json

from graph.state import AgentGraph
from utils.node_utils import (
    utc_now,
    start_timer,
    duration_ms,
    add_node_history,
)
from logger.logging import logger
from llm.model import invoke

NODE_NAME = "Classify"

QUALITY_THRESHOLD = 0.70

CATEGORIES = [
    "Automation",
    "Process Improvement",
    "Product",
    "Technology",
    "Cost Reduction",
    "Customer Experience",
    "Employee Experience",
    "Data & Analytics",
    "Quality Improvement",
    "Sustainability",
]


def classify_model(submission: str) -> dict:
    """
    Ask the LLM to categorize the idea and score its quality.
    """

    prompt = f"""
You are an idea evaluation assistant.

The user has submitted a short idea of around 3-4 lines.

Evaluate the idea and return ONLY valid JSON.

The idea must be categorized into exactly ONE of these categories:

{CATEGORIES}

Also score the idea on these dimensions from 0.0 to 1.0:

1. clarity
   - How clearly is the problem or opportunity explained?

2. impact
   - How much potential business/user value could the idea provide?

3. feasibility
   - How realistic does the proposed idea appear?

4. specificity
   - How specific and concrete is the idea?

IMPORTANT:
- Do not reject the idea yourself.
- Do not decide whether it needs manual review.
- Only categorize and score it.
- Scores must be numbers between 0.0 and 1.0.

Return exactly this structure:

{{
    "category": "one category from the list",
    "scores": {{
        "clarity": 0.0,
        "impact": 0.0,
        "feasibility": 0.0,
        "specificity": 0.0
    }},
    "reason": "short explanation"
}}

IDEA:
{submission}
"""

    response_text = invoke(prompt)

    return json.loads(response_text)


def calculate_idea_score(scores: dict) -> float:
    """
    Calculate the overall idea quality score.

    Current weights:
    clarity       = 25%
    impact        = 30%
    feasibility   = 20%
    specificity   = 25%
    """

    score = (
        scores["clarity"] * 0.25
        + scores["impact"] * 0.30
        + scores["feasibility"] * 0.20
        + scores["specificity"] * 0.25
    )

    return round(score, 2)


def classify_node(state: AgentGraph) -> dict:

    started_at = utc_now()
    timer = start_timer()

    run_id = state["run_id"]
    correlation_id = state["correlation_id"]

    previous_node = state.get("current_node")

    node_input = {
        "submission_received": bool(state.get("submission"))
    }

    logger.info(
        "Node started",
        extra={
            "extra_fields": {
                "event": "node_start",
                "run_id": run_id,
                "correlation_id": correlation_id,
                "node": NODE_NAME,
            }
        }
    )

    try:

        submission = state.get("submission", "")

        if not submission:
            raise ValueError(
                "Submission is required for classification"
            )

        # LLM classification + evaluation
        llm_result = classify_model(submission)

        category = llm_result["category"]
        scores = llm_result["scores"]
        reason = llm_result.get("reason", "")

        # Validate category
        if category not in CATEGORIES:
            raise ValueError(
                f"Invalid category returned by LLM: {category}"
            )

        # Validate scores
        required_scores = [
            "clarity",
            "impact",
            "feasibility",
            "specificity",
        ]

        for score_name in required_scores:

            if score_name not in scores:
                raise ValueError(
                    f"Missing score: {score_name}"
                )

            score = scores[score_name]

            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"{score_name} must be between 0 and 1"
                )
            
        # Calculate overall idea score

        idea_score = calculate_idea_score(scores)

        idea_assessment = {
            "idea_score": idea_score,
            "scores": scores,
            "reason": reason,
        }

        classification = {
            "category": category,
        }

        node_output = {
            "classification": classification,
            "idea_assessment": idea_assessment,
            "current_node": NODE_NAME,
            "status": "CLASSIFIED",
        }

        finished_at = utc_now()
        elapsed = duration_ms(timer)

        history = add_node_history(
            state=state,
            node_name=NODE_NAME,
            run_id=run_id,
            correlation_id=correlation_id,
            node_input=node_input,
            node_output=node_output,
            started_at=started_at,
            finished_at=finished_at,
            duration=elapsed,
            success=True,
            previous_node=previous_node,
            next_node=None,
        )

        result = {
            **node_output,
            "node_history": history,
        }

        print("\n========== CLASSIFICATION ==========")
        print(f"Category       : {category}")
        print(f"Clarity        : {scores['clarity']}")
        print(f"Impact         : {scores['impact']}")
        print(f"Feasibility    : {scores['feasibility']}")
        print(f"Specificity    : {scores['specificity']}")
        print(f"Idea Score     : {idea_score}")
        print(f"Threshold      : {QUALITY_THRESHOLD}")

        # Temporary routing
        if idea_score < QUALITY_THRESHOLD:
            next_node = "Manual Review"
        else:
            next_node = "Duplicate Check"
        print(f"Next Node      : {next_node}")
        print("====================================\n")
        logger.info(
            "Node completed",
            extra={
                "extra_fields": {
                    "event": "node_end",
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                    "node": NODE_NAME,
                    "duration_ms": round(elapsed, 2),
                    "success": True,
                    "idea_score": idea_score,
                    "next_node": next_node,
                }
            }
        )

        return result

    except Exception as exc:

        elapsed = duration_ms(timer)

        logger.error(
            "Node failed",
            extra={
                "extra_fields": {
                    "event": "node_error",
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                    "node": NODE_NAME,
                    "duration_ms": round(elapsed, 2),
                    "success": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            }
        )

        raise