from langchain_openai import AzureOpenAIEmbeddings #type:ignore
from dotenv import load_dotenv #type:ignore
import os

load_dotenv()

def get_embeddings():

    embeddings=AzureOpenAIEmbeddings(
        azure_endpoint=os.getenv("AZURE_EMBEDDING_ENDPOINT"),
        api_key=os.getenv("AZURE_EMBEDDING_API_KEY"),
        api_version=os.getenv("AZURE_EMBEDDING_API_VERSION"),
        azure_deployment=os.getenv("AZURE_EMBEDDING_DEPLOYMENT")
    )

    return embeddings

embedding_model=get_embeddings()