from langchain_community.vectorstores import FAISS

from llm.embeddings import embedding_model


VECTORSTORE_PATH = "vectorstore/ideas"


def load_vectorstore():

    vectorstore = FAISS.load_local(
        VECTORSTORE_PATH,
        embedding_model,
        allow_dangerous_deserialization=True
    )

    return vectorstore