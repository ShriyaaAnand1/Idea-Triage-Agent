
import uuid

from langgraph.types import Command

from database.connection import get_checkpointer
from database.users import validate_permitted_user
from database.runs import (
    create_run,
    update_run_status,
    get_latest_incomplete_run_by_user,
)
from database.reviewer_decisions import create_reviewer_decision
from graph.workflow import create_graph
from utils.thread_utils import create_thread_id


def create_run_id() -> str:
    return str(uuid.uuid4())


def create_correlation_id() -> str:
    return str(uuid.uuid4())


def is_workflow_complete(state) -> bool:
    return not state.next


def has_pending_interrupt(state) -> bool:
    return any(task.interrupts for task in state.tasks)


def get_pending_task_id(state) -> str:
    """Read the application task ID from the interrupt payload."""
    for task in state.tasks:
        for interrupt in task.interrupts:
            payload = getattr(interrupt, "value", None)

            if isinstance(payload, dict):
                task_id = payload.get("task_id")

                if task_id:
                    return str(uuid.UUID(str(task_id)))

    raise ValueError(
        "A pending interrupt was found, but its payload "
        "does not contain task_id."
    )


def finish_run(state):
    """Mark the run complete after reaching a terminal graph state."""
    values = state.values
    run_id = values.get("run_id")

    if not run_id:
        raise ValueError("run_id is missing from graph state.")

    status = values.get("status") or "COMPLETED"

    # Do not overwrite a meaningful terminal business outcome.
    terminal_statuses = {
        "COMPLETED",
        "REJECTED",
        "DUPLICATE",
        "DUPLICATE_DETECTED",
        "ESCALATED",
        "HUMAN_REVIEW",
    }

    if status not in terminal_statuses:
        status = "COMPLETED"

    update_run_status(
        run_id=run_id,
        status=status,
        completed=True,
    )


def get_reviewer_decision():
    """Collect a decision from an authorized reviewer."""
    while True:
        reviewer_id = input("Enter reviewer ID: ").strip()

        if validate_permitted_user(reviewer_id, "REVIEWER"):
            break

        print("Invalid, inactive, or unauthorized reviewer.")

    print("\nHUMAN APPROVAL")
    print("1. Approve")
    print("2. Reject")
    print("3. Need Improvement")

    while True:
        choice = input("Enter your choice: ").strip()

        if choice == "1":
            return reviewer_id, {
                "action": "approve",
                "comment": "",
            }

        if choice == "2":
            comment = input("Enter rejection comment: ").strip()

            if comment:
                return reviewer_id, {
                    "action": "reject",
                    "comment": comment,
                }

            print("Rejection comment cannot be empty.")

        elif choice == "3":
            comment = input("Enter improvement comment: ").strip()

            if comment:
                return reviewer_id, {
                    "action": "improve",
                    "comment": comment,
                }

            print("Improvement comment cannot be empty.")

        else:
            print("Invalid choice. Enter 1, 2, or 3.")


def persist_decision(
    state,
    thread_id,
    task_id,
    reviewer_id,
    decision,
):
    values = state.values

    create_reviewer_decision(
        run_id=values["run_id"],
        thread_id=thread_id,
        task_id=task_id,
        reviewer_user_id=reviewer_id,
        action=decision["action"],
        comment=decision.get("comment", ""),
    )


def handle_workflow(graph, config, thread_id):
    """Continue graph execution until completion or another interrupt."""
    while True:
        state = graph.get_state(config)

        if not state.values:
            raise ValueError("No saved workflow state was found.")

        if is_workflow_complete(state):
            finish_run(state)
            print("\nWORKFLOW COMPLETED")
            return

        if has_pending_interrupt(state):
            task_id = get_pending_task_id(state)

            print(f"\nApproval task ID: {task_id}")

            reviewer_id, decision = get_reviewer_decision()

            # Resume the exact paused thread.
            graph.invoke(
                Command(resume=decision),
                config=config,
            )

            # Persist after the graph accepts the decision.
            # See the note below about crash recovery between these steps.
            persist_decision(
                state=state,
                thread_id=thread_id,
                task_id=task_id,
                reviewer_id=reviewer_id,
                decision=decision,
            )

            continue

        # Continue a checkpoint that is not currently interrupted.
        graph.invoke(None, config=config)


def start_new_workflow(user_id):
    if not validate_permitted_user(user_id, "USER"):
        raise ValueError("User is not permitted to submit ideas.")

    submission = input("\nEnter your idea submission: ").strip()

    if not submission:
        print("Idea submission cannot be empty.")
        return

    run_id = create_run_id()
    thread_id = create_thread_id()
    correlation_id = create_correlation_id()

    create_run(
        run_id=run_id,
        thread_id=thread_id,
        correlation_id=correlation_id,
        user_id=user_id,
        status="IN_PROGRESS",
        current_node="Submission",
    )

    initial_state = {
        "user_id": user_id,
        "run_id": run_id,
        "thread_id": thread_id,
        "correlation_id": correlation_id,
        "submission": submission,
    }

    config = {"configurable": {"thread_id": thread_id}}

    with get_checkpointer() as checkpointer:
        checkpointer.setup()
        graph = create_graph(checkpointer)

        graph.invoke(initial_state, config=config)

        handle_workflow(
            graph=graph,
            config=config,
            thread_id=thread_id,
        )


def resume_existing_workflow(user_id, thread_id):
    print("\nRECOVERING WORKFLOW")

    config = {"configurable": {"thread_id": thread_id}}

    with get_checkpointer() as checkpointer:
        checkpointer.setup()
        graph = create_graph(checkpointer)

        state = graph.get_state(config)

        if not state.values:
            print("No saved workflow state was found.")
            return

        # Prevent a user from resuming another user's run.
        if state.values.get("user_id") != user_id:
            raise PermissionError(
                "This workflow does not belong to the specified user."
            )

        print("Current node:", state.values.get("current_node"))
        print("Status:", state.values.get("status"))

        if is_workflow_complete(state):
            finish_run(state)
            print("Workflow already completed.")
            return

        if not has_pending_interrupt(state):
            print("Resuming from saved checkpoint...")
            graph.invoke(None, config=config)

        handle_workflow(
            graph=graph,
            config=config,
            thread_id=thread_id,
        )


def main():
    print("\nIDEA TRIAGE AGENT")

    user_id = input("Enter your user ID: ").strip()

    if not user_id:
        print("User ID cannot be empty.")
        return

    if not validate_permitted_user(user_id, "USER"):
        print("User is not permitted to submit ideas.")
        return

    active_run = get_latest_incomplete_run_by_user(user_id)

    if active_run:
        print(
            "\nFound an unfinished run:",
            active_run["run_id"],
        )

        print("1. Resume unfinished run")
        print("2. Submit a new idea")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            resume_existing_workflow(
                user_id=user_id,
                thread_id=active_run["thread_id"],
            )
        elif choice == "2":
            start_new_workflow(user_id)
        else:
            print("Invalid choice.")
    else:
        start_new_workflow(user_id)


if __name__ == "__main__":
    main()