from difflib import SequenceMatcher

from graph.state import AgentGraph


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

        return {
            "duplicate_found": False,
            "duplicate_matches": [],
            "current_node": node_name,
            "status": "DUPLICATE_CHECKED",
        }

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

    return {
        "duplicate_found": duplicate_found,
        "duplicate_matches": top_matches,
        "current_node": node_name,
        "status": (
            "DUPLICATE_FOUND"
            if duplicate_found
            else "DUPLICATE_CHECKED"
        ),
    }