from graph.nodes.submission import submission_node
from graph.nodes.classify import classify_node

idea = """
Automate the manual approval process for purchase requests.
The system should automatically route requests to the correct approver
and reduce the amount of time employees spend waiting for approvals.
"""

state = {
    "submission": idea
}

submission_result = submission_node(state)
state.update(submission_result)
classify_result = classify_node(state)
state.update(classify_result)

print("\nFINAL STATE:")
print(state)