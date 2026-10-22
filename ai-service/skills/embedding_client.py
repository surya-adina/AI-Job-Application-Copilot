import os

import psycopg

from skills.embedding_store import save_skill_embeddings, stored_skills

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

_client = None


def get_embedding_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(max_retries=2, timeout=30)
    return _client


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = get_embedding_client().embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def ensure_skill_embeddings(connection: psycopg.Connection, skills: list[str]) -> None:
    """Embed and store any skill names that are not in SkillEmbedding yet."""
    unique = sorted({skill for skill in skills if skill.strip()})
    if not unique:
        return

    missing = [skill for skill in unique if skill not in stored_skills(connection, unique)]
    if missing:
        save_skill_embeddings(connection, dict(zip(missing, embed(missing))))
