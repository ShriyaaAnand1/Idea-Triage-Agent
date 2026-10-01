from langgraph.types import Command

from database.connection import get_checkpointer
from database.users import create_user, get_thread_id
from graph.workflow import create_graph
from utils.thread_utils import create_thread_id

def get_reviewer_decision():
    """
    Get the reviewer's decision from the user.
    """
    print("\n========== HUMAN APPROVAL ==========")
    print("\nReviewer decision:")
    print("1. Approve")
    print("2. Reject")
    print("3. Need Improvement")

    decision = input("\nEnter your choice: ").strip()
    decision_map = {
        "1": "approve",
        "2": "reject",
        "3": "improve",
    }
    action = decision_map.get(decision)

    if action is None:
        print("\nInvalid choice.")
        return None

    comment = ""
    if action == "improve":
        comment = input(
            "\nEnter improvement suggestions:\n"
        ).strip()

        if not comment:
            print(
                "\nImprovement suggestion cannot be empty."
            )
            return None

    return {
        "action": action,
        "comment": comment,
    }

def continue_workflow(graph, config, result):
    """
    Continue the workflow when LangGraph has reached
    the Human Approval interrupt.
    """

    while "__interrupt__" in result:
        decision = get_reviewer_decision()
        if decision is None:
            return
        print("\n========== CONTINUING WORKFLOW ==========")
        result = graph.invoke(
            Command(
                resume=decision
            ),
            config
        )

    # Workflow finished normally
    state = graph.get_state(config)

    print("\n========== WORKFLOW COMPLETED ==========")
    print(
        "Status:",
        state.values.get("status")
    )
    print(
        "Current node:",
        state.values.get("current_node")
    )

def main():

    print("\n========== IDEA TRIAGE AGENT ==========")
    print("1. New User")
    print("2. Existing User")

    choice = input("\nEnter your choice: ").strip()

    # NEW USER
    if choice == "1":
        user_name = input("\nEnter your name: ").strip()
        if not user_name:
            print("\nUser name cannot be empty.")
            return
        existing_thread_id = get_thread_id(user_name)
        if existing_thread_id:
            print("\nUser already exists.")
            print(
                "Please select 'Existing User' "
                "to continue."
            )
            return

        thread_id = create_thread_id()

        create_user(
            user_name=user_name,
            thread_id=thread_id
        )

        print("\nUser created successfully.")
        idea = input("\nEnter your idea:\n").strip()

        if not idea:
            print("\nIdea cannot be empty.")
            return

        initial_state = {
            "thread_id": thread_id,
            "submission": idea,
        }

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        # Start workflow
        with get_checkpointer() as checkpointer:
            checkpointer.setup()
            graph = create_graph(checkpointer)
            print(
                "\n========== STARTING WORKFLOW =========="
            )
            result = graph.invoke(
                initial_state,
                config
            )
         # If Human Approval is reached, ask reviewer.
            if "__interrupt__" in result:
                continue_workflow(
                    graph,
                    config,
                    result
                )
            else:
                state = graph.get_state(config)
                print(
                    "\n========== WORKFLOW COMPLETED =========="
                )
                print(
                    "Status:",
                    state.values.get("status")
                )
                print(
                    "Current node:",
                    state.values.get("current_node")
                )
    
    # EXISTING USER
    elif choice == "2":
        user_name = input("\nEnter your name: ").strip()
        if not user_name:
            print("\nUser name cannot be empty.")
            return
        # Retrieve thread
        thread_id = get_thread_id(user_name)
        if not thread_id:
            print("\nUser not found.")
            print(
                "Please select 'New User'."
            )
            return
        print("\nUser found.")
        print(
            "Thread ID:",
            thread_id
        )
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        # Open checkpointer
        with get_checkpointer() as checkpointer:
            checkpointer.setup()
            graph = create_graph(checkpointer)
                # Read latest checkpoint

            state = graph.get_state(config)
            if not state.values:
                print(
                    "\nNo existing workflow found "
                    "for this user."
                )
                return
            print(
                "\n========== RECOVERING WORKFLOW =========="
            )
            print(
                "Current node:",
                state.values.get("current_node")
            )
            print(
                "Status:",
                state.values.get("status")
            )
    
            # Workflow was stopped while waiting for Human Approval.
            if state.tasks and any(
                task.interrupts
                for task in state.tasks
            ):
                print(
                    "\nWorkflow was waiting for "
                    "human approval when the process stopped."
                )
                decision = get_reviewer_decision()
                if decision is None:
                    return
                print(
                    "\n========== RESUMING WORKFLOW =========="
                )
                result = graph.invoke(
                    Command(
                        resume=decision
                    ),
                    config
                )
                # There may be another approval after an improvement.
                if "__interrupt__" in result:
                    continue_workflow(
                        graph,
                        config,
                        result
                    )
                else:
                    final_state = graph.get_state(config)
                    print(
                        "\n========== WORKFLOW COMPLETED =========="
                    )
                    print(
                        "Status:",
                        final_state.values.get("status")
                    )
                    print(
                        "Current node:",
                        final_state.values.get("current_node")
                    )
                return
            
            # Process stopped while workflow was executing Resume from the latest SQL checkpoint.
            if state.next:
                print(
                    "\nThe previous process stopped "
                    "before the workflow completed."
                )
                print(
                    "Resuming from the saved checkpoint..."
                )
                result = graph.invoke(
                    None,
                    config
                )
                if "__interrupt__" in result:
                    continue_workflow(
                        graph,
                        config,
                        result
                    )
                else:
                    final_state = graph.get_state(config)
                    print(
                        "\n========== WORKFLOW COMPLETED =========="
                    )
                    print(
                        "Status:",
                        final_state.values.get("status")
                    )
                    print(
                        "Current node:",
                        final_state.values.get("current_node")
                    )
                return
           
            # Workflow already completed.
            print(
                "\n========== WORKFLOW ALREADY COMPLETED =========="
            )
            print(
                "Status:",
                state.values.get("status")
           )
            print(
                "Current node:",
                state.values.get("current_node")
            )
    else:
        print("\nInvalid choice.")

if __name__ == "__main__":
    main()
