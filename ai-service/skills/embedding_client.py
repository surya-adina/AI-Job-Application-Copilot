import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_embedding_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def embed_texts(texts: list[str]) -> dict[str, list[float]]:
    if not texts:
        return {}

    response = _embedding_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )

    return {
        text: item.embedding
        for text, item in zip(texts, response.data)
    }