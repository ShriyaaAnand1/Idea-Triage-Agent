import uuid

from langgraph.types import Command
from database.connection import get_checkpointer
from database.threads import (
    create_thread,
    get_active_thread,
    mark_thread_completed,
)
from graph.workflow import create_graph
from utils.thread_utils import create_thread_id

# ID helpers

def create_run_id() -> str:
    return str(uuid.uuid4())
def create_correlation_id() -> str:
    return str(uuid.uuid4())

# Workflow completion

def is_workflow_complete(state) -> bool:
    return not state.next

# Check for actual LangGraph interrupt

def has_pending_interrupt(state) -> bool:
    """
    Return True only when a task contains
    an actual LangGraph interrupt.
    """
    for task in state.tasks:

        if task.interrupts:
            return True

    return False

# Human approval

def get_reviewer_decision(allow_improve=True):

    print("\nHUMAN APPROVAL")

    print("1. Approve")
    print("2. Reject")

    if allow_improve:
        print("3. Need Improvement")

    while True:

        choice = input(
            "\nEnter your choice: "
        ).strip()

        if choice == "1":

            return {
                "action": "approve",
                "comment": ""
            }

        elif choice == "2":

            comment = input(
                "Enter rejection comment: "
            ).strip()

            return {
                "action": "reject",
                "comment": comment
            }

        elif choice == "3" and allow_improve:

            comment = input(
                "Enter improvement comment: "
            ).strip()

            if not comment:
                print("Comment cannot be empty.")
                continue

            return {
                "action": "improve",
                "comment": comment
            }

        else:

            print("Invalid choice. Please try again.")


# Start new workflow

def start_new_workflow(user_name: str):

    thread_id = create_thread_id()

    create_thread(
        user_name=user_name,
        thread_id=thread_id
    )

    run_id = create_run_id()
    correlation_id = create_correlation_id()

    submission = input(
        "\nEnter your idea submission: "
    ).strip()

    initial_state = {
        "thread_id": thread_id,
        "run_id": run_id,
        "correlation_id": correlation_id,
        "submission": submission,
    }

    with get_checkpointer() as checkpointer:

        checkpointer.setup()

        graph = create_graph(checkpointer)

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        graph.invoke(
            initial_state,
            config
        )

        handle_workflow(
            graph=graph,
            config=config,
            thread_id=thread_id
        )

# Resume existing workflow

def resume_existing_workflow(
    user_name: str,
    thread_id: str
):

    print("\nRECOVERING WORKFLOW")

    with get_checkpointer() as checkpointer:

        checkpointer.setup()

        graph = create_graph(checkpointer)

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        saved_state = graph.get_state(config)

        print(
            f"Current node: "
            f"{saved_state.values.get('current_node')}"
        )

        print(
            f"Status: "
            f"{saved_state.values.get('status')}"
        )
        # Already completed
        if is_workflow_complete(saved_state):

            mark_thread_completed(thread_id)

            print("Workflow already completed.")

            return

        # Actual LangGraph interrupt
        if has_pending_interrupt(saved_state):

            reviewer_decision = get_reviewer_decision()

            graph.invoke(
                Command(
                    resume=reviewer_decision
                ),
                config
            )

        # No interrupt
        else:

            print(
                "Resuming from saved checkpoint..."
            )

            graph.invoke(
                None,
                config
            )

        handle_workflow(
            graph=graph,
            config=config,
            thread_id=thread_id
        )

# Continue workflow

def handle_workflow(
    graph,
    config,
    thread_id
):

    while True:

        state = graph.get_state(config)
        # Completed
        if is_workflow_complete(state):

            print("\nWORKFLOW COMPLETED")

            mark_thread_completed(thread_id)

            return
        # Actual interrupt
        if has_pending_interrupt(state):

            reviewer_decision = get_reviewer_decision()

            graph.invoke(
                Command(
                    resume=reviewer_decision
                ),
                config
            )

            continue

        # Normal continuation

        graph.invoke(
            None,
            config
        )

# Main

def main():
    print("\nIDEA TRIAGE AGENT")

    user_name = input(
        "\nEnter your user name: "
    ).strip()

    if not user_name:

        print("User name cannot be empty.")

        return

    # Look only for an unfinished workflow
    active_thread = get_active_thread(user_name)

    if active_thread:

        resume_existing_workflow(
            user_name=user_name,
            thread_id=active_thread
        )

    else:
        start_new_workflow(user_name)

if __name__ == "__main__":
    main()