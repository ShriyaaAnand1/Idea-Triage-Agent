from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from llm.embeddings import embedding_model


IDEAS_FILE = "data/ideas.txt"
VECTORSTORE_PATH = "vectorstore/ideas"


def load_ideas():

    with open(
        IDEAS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        content = file.read()

    ideas = [
        idea.strip()
        for idea in content.split("\n\n")
        if idea.strip()
    ]

    return ideas


def create_documents():

    ideas = load_ideas()

    documents = []

    for idea in ideas:

        document = Document(
            page_content=idea
        )

        documents.append(document)

    return documents


def create_vectorstore():

    documents = create_documents()

    vectorstore = FAISS.from_documents(
        documents,
        embedding_model
    )

    return vectorstore


def save_vectorstore(vectorstore):

    vectorstore.save_local(
        VECTORSTORE_PATH
    )


def main():

    print("Loading ideas...")

    documents = create_documents()

    print(
        f"Found {len(documents)} ideas."
    )

    print("Creating embeddings...")

    vectorstore = FAISS.from_documents(
        documents,
        embedding_model
    )

    print("Saving vector store...")

    save_vectorstore(vectorstore)

    print(
        "\nVector store created successfully."
    )


if __name__ == "__main__":
    main()