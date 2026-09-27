from difflib import SequenceMatcher

from graph.state import AgentGraph


IDEAS_FILE = "data/ideas.txt"

SIMILARITY_THRESHOLD = 0.80
TOP_K = 3


def normalize_text(text: str) -> str:
    """
    Normalize text before comparing ideas.
    """

    return " ".join(
        text.lower().split()
    )


def calculate_similarity(
    new_idea: str,
    existing_idea: str,
) -> float:
    """
    Calculate text similarity between
    two ideas.

    Temporary implementation.

    Later this will be replaced by
    embedding/vector-store similarity.
    """

    return round(
        SequenceMatcher(
            None,
            normalize_text(new_idea),
            normalize_text(existing_idea),
        ).ratio(),
        2,
    )


def load_existing_ideas() -> list[str]:
    """
    Load past ideas from the text file.
    """

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

    # --------------------------------
    # Load previous ideas
    # --------------------------------

    existing_ideas = load_existing_ideas()

    if not existing_ideas:

        print(
            "\nNo existing ideas found."
        )

        return {
            "is_duplicate": False,
            "duplicate_matches": [],
            "current_node": node_name,
            "status": "DUPLICATE_CHECKED",
        }

    # --------------------------------
    # Compare against every old idea
    # --------------------------------

    matches = []

    for idea in existing_ideas:

        similarity = calculate_similarity(
            submission,
            idea,
        )

        matches.append(
            {
                "idea": idea,
                "similarity": similarity,
            }
        )

    # --------------------------------
    # Sort by highest similarity
    # --------------------------------

    matches.sort(
        key=lambda match: match["similarity"],
        reverse=True,
    )

    # --------------------------------
    # Keep only top 3
    # --------------------------------

    top_matches = matches[:TOP_K]

    # --------------------------------
    # Duplicate decision
    # --------------------------------

    is_duplicate = (
        top_matches[0]["similarity"]
        >= SIMILARITY_THRESHOLD
    )

    # --------------------------------
    # Testing output
    # --------------------------------

    print(
        "\n========== DUPLICATE CHECK =========="
    )

    print("\nNew Idea:")
    print(submission)

    print("\nTop Matches:")

    for index, match in enumerate(
        top_matches,
        start=1,
    ):

        print(
            f"\nMatch {index}"
        )

        print(
            f"Idea       : {match['idea']}"
        )

        print(
            f"Similarity : {match['similarity']}"
        )

    print(
        f"\nThreshold  : "
        f"{SIMILARITY_THRESHOLD}"
    )

    print(
        f"Duplicate  : "
        f"{'YES' if is_duplicate else 'NO'}"
    )

    print(
        "=====================================\n"
    )

    # --------------------------------
    # Return state
    # --------------------------------

    return {
        "is_duplicate": is_duplicate,
        "duplicate_matches": top_matches,
        "current_node": node_name,
        "status": (
            "DUPLICATE_FOUND"
            if is_duplicate
            else "DUPLICATE_CHECKED"
        ),
    }