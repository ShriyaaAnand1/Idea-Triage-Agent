
from graph.state import AgentGraph
from vectorstore.load_vs import load_vectorstore, VECTORSTORE_PATH


def finalize_node(state: AgentGraph) -> dict:
    node_name = "Finalize"

    thread_id = str(state.get("thread_id") or "").strip()
    task_id = str(state.get("task_id") or "").strip()
    submission = state.get("submission")
    draft_summary = str(state.get("draft_summary") or "").strip()

    if not thread_id:
        raise ValueError("Cannot finalize: thread_id is missing.")

    if not submission:
        raise ValueError("Cannot finalize: original submission is missing.")

    # Adapt this extraction to your actual submission structure.
    if isinstance(submission, str):
        idea_text = submission.strip()
    elif isinstance(submission, dict):
        idea_text = str(
            submission.get("idea")
            or submission.get("description")
            or submission.get("title")
            or ""
        ).strip()
    else:
        idea_text = str(submission).strip()

    if not idea_text:
        raise ValueError("Cannot finalize: idea text is empty.")

    vectorstore = load_vectorstore()

    # Avoid inserting the same workflow idea again on a retry.
    already_stored = any(
        document.metadata.get("thread_id") == thread_id
        for document_id in vectorstore.index_to_docstore_id.values()
        if not isinstance(
            (document := vectorstore.docstore.search(document_id)),
            str,
        )
    )

    if not already_stored:
        document_text = idea_text

        if draft_summary:
            document_text += f"\n\nFinal summary: {draft_summary}"

        vectorstore.add_texts(
            texts=[document_text],
            metadatas=[{
                "thread_id": thread_id,
                "task_id": task_id,
                "status": "APPROVED",
                "source": "idea_triage_agent",
            }],
            ids=[thread_id],
        )

        vectorstore.save_local(VECTORSTORE_PATH)
        print(f"Approved idea stored in FAISS: {thread_id}")
    else:
        print(f"Idea already indexed: {thread_id}")

    print("\nIdea approved successfully.")
    print("\nFinal Summary:")
    print(draft_summary)

    return {
        "current_node": node_name,
        "status": "FINALIZED",
    }
