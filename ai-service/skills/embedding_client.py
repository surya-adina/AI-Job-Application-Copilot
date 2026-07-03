import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_embedding_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

_embedding_cache: dict[str, list[float]] = {}


def embed_texts(texts: list[str]) -> dict[str, list[float]]:
    if not texts:
        return {}

    unique_texts = sorted(set(texts))

    cached_vectors = {
        text: _embedding_cache[text]
        for text in unique_texts
        if text in _embedding_cache
    }

    missing_texts = [
        text for text in unique_texts
        if text not in _embedding_cache
    ]

    if missing_texts:
        response = _embedding_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=missing_texts,
        )

        for text, item in zip(missing_texts, response.data):
            _embedding_cache[text] = item.embedding

    return {
        text: _embedding_cache[text]
        for text in unique_texts
    }