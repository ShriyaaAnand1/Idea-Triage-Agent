from graph.nodes.duplicate_check import duplicate_check_node


state = {
    "submission": "Create an AI chatbot to answer employee HR questions."
}


result = duplicate_check_node(state)

print("\n========== RESULT ==========")
print(result)
print("============================")