from graph.workflow import graph


initial_state = {
    "submission": (
        "Develop an AI system that predicts "
        "customer demand and recommends optimal "
        "inventory levels for each product."
    )
}


print("\nStarting Idea Triage workflow...\n")

result = graph.invoke(initial_state)


print("\n========== WORKFLOW RESULT ==========")

print("\nSubmission:")
print(result.get("submission"))

print("\nClassification:")
print(result.get("classification"))

print("\nIdea Assessment:")
print(result.get("idea_assessment"))

print("\nDuplicate:")
print(result.get("is_duplicate"))

print("\nTop Duplicate Matches:")
for match in result.get("duplicate_matches", []):
    print(match)

print("\nDraft Summary:")
print(result.get("draft"))

print("\nFinal Status:")
print(result.get("status"))

print("\n=====================================")