import os
from dotenv import load_dotenv
from openai import OpenAI
from skills.embedding_store import get_skill_embedding, save_skill_embedding

load_dotenv()

_embedding_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

_memory_cache: dict[str, list[float]] = {}

def embed_texts(texts: list[str]) -> dict[str, list[float]]:
    if not texts:
        return {}

    unique_texts = sorted(set(texts))
    vectors_by_text: dict[str, list[float]] = {}

    missing_from_openai = []

    for text in unique_texts:
        if text in _memory_cache:
            vectors_by_text[text] = _memory_cache[text]
            continue

        stored_vector = get_skill_embedding(text)

        if stored_vector:
            _memory_cache[text] = stored_vector
            vectors_by_text[text] = stored_vector
            continue

        missing_from_openai.append(text)

    if missing_from_openai:
        response = _embedding_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=missing_from_openai,
        )

        for text, item in zip(missing_from_openai, response.data):
            vector = item.embedding
            _memory_cache[text] = vector
            vectors_by_text[text] = vector
            save_skill_embedding(text, vector)

    return vectors_by_text