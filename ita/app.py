from langgraph.types import Command

from graph.workflow import graph


def main():

    print("\n===================================")
    print("       IDEA TRIAGE AGENT")
    print("===================================\n")

    submission = input(
        "Enter your idea:\n> "
    ).strip()

    if not submission:
        print("Idea cannot be empty.")
        return

    initial_state = {
        "submission": submission,
    }

    config = {
        "configurable": {
            "thread_id": "idea-session"
        }
    }

    print("\nStarting graph...\n")

    result = graph.invoke(
        initial_state,
        config,
    )

    while "__interrupt__" in result:

        print(
            "\n========== HUMAN APPROVAL =========="
        )

        print("\nWhat would you like to do?")

        print("1. Approve")
        print("2. Reject")
        print("3. Need Improvement")

        choice = input(
            "\nEnter your choice: "
        ).strip()

        if choice == "1":

            action = "approve"

            comment = ""

        elif choice == "2":

            action = "reject"

            comment = ""

        elif choice == "3":

            action = "improve"

            comment = input(
                "\nEnter your suggestions for improvement:\n> "
            ).strip()

            if not comment:

                print(
                    "\nImprovement suggestions "
                    "cannot be empty."
                )

                continue

        else:

            print(
                "\nInvalid choice. "
                "Please enter 1, 2, or 3."
            )

            continue

        result = graph.invoke(
            Command(
                resume={
                    "action": action,
                    "comment": comment,
                }
            ),
            config,
        )

    print("\n===================================")
    print("          GRAPH COMPLETED")
    print("===================================")


if __name__ == "__main__":
    main()
    