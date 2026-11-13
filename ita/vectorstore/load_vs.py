
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from llm.embeddings import embedding_model


IDEAS_FILE = "data/ideas.txt"
VECTORSTORE_PATH = "vectorstore/ideas"


def load_ideas():
    with open(IDEAS_FILE, "r", encoding="utf-8") as file:
        content = file.read()

    return [
        idea.strip()
        for idea in content.split("\n\n")
        if idea.strip()
    ]


def create_vectorstore():
    ideas = load_ideas()

    if not ideas:
        raise ValueError("No initial ideas found in data/ideas.txt")

    documents = [
        Document(
            page_content=idea,
            metadata={
                "source": "ideas.txt",
                "status": "APPROVED",
            },
        )
        for idea in ideas
    ]

    vectorstore = FAISS.from_documents(
        documents,
        embedding_model,
    )

    Path(VECTORSTORE_PATH).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    vectorstore.save_local(VECTORSTORE_PATH)

    return vectorstore


def load_vectorstore():
    index_file = Path(VECTORSTORE_PATH) / "index.faiss"

    if not index_file.exists():
        return create_vectorstore()

    return FAISS.load_local(
        VECTORSTORE_PATH,
        embedding_model,
        allow_dangerous_deserialization=True,
    )
