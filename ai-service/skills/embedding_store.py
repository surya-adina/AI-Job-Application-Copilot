"""Postgres/pgvector access for skill-name embeddings.

Only skill names are stored. Resume sentences are embedded on the fly and
compared in SQL as query vectors, never persisted.
"""

import os

import psycopg


def get_connection() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg.connect(database_url, autocommit=True)


def to_vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(value) for value in embedding) + "]"


def stored_skills(connection: psycopg.Connection, skills: list[str]) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT "skill"
            FROM "SkillEmbedding"
            WHERE "skill" = ANY(%s) AND "embedding" IS NOT NULL
            """,
            (skills,),
        )
        return {row[0] for row in cursor.fetchall()}


def save_skill_embeddings(connection: psycopg.Connection, vectors: dict[str, list[float]]) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO "SkillEmbedding" ("id", "skill", "embedding")
            VALUES (gen_random_uuid(), %s, %s::vector)
            ON CONFLICT ("skill")
            DO UPDATE SET "embedding" = EXCLUDED."embedding"
            """,
            [(skill, to_vector_literal(vector)) for skill, vector in vectors.items()],
        )
