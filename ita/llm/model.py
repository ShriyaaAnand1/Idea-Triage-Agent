import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

llm = OpenAI(
    base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY")
)

deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")


def invoke(prompt):

    response = llm.responses.create(
        model=deployment_name,
        input=prompt
    )

    return response.output_text