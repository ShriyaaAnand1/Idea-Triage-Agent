from langgraph.types import Command

from graph.workflow import graph


initial_state = {
    "submission": (
        "Develop an AI system that predicts customer "
        "demand and recommends optimal inventory levels "
        "for each product."
    )
}


config = {
    "configurable": {
        "thread_id": "hitl-test-001"
    }
}


print("\nStarting graph...\n")


result = graph.invoke(
    initial_state,
    config
)


print("\n========== GRAPH PAUSED ==========")

print("\nResult:")
print(result)


interrupts = result.get("__interrupt__")


if interrupts:

    interrupt_value = interrupts[0].value

    print("\nApproval Task ID:")
    print(
        interrupt_value.get(
            "task_id"
        )
    )

    print("\nApproval Status:")
    print(
        interrupt_value.get(
            "status"
        )
    )

    print("\nThe graph is now waiting for reviewer decision.")

else:

    print("\nNo interrupt found.")


print("\n==================================")