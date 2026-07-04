import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg.connect(database_url)

def save_skill_embedding(skill: str, embedding: list[float]) -> None:
    vector_value = "[" + ",".join(str(value) for value in embedding) + "]"

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO "SkillEmbedding" ("id", "skill", "embedding")
                VALUES (gen_random_uuid(), %s, %s::vector)
                ON CONFLICT ("skill")
                DO UPDATE SET "embedding" = EXCLUDED."embedding"
                """,
                (skill, vector_value),
            )

def get_skill_embedding(skill: str) -> list[float] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT "embedding"::text
                FROM "SkillEmbedding"
                WHERE "skill" = %s
                """,
                (skill,),
            )

            row = cursor.fetchone()

    if not row:
        return None

    vector_text = row[0].strip("[]")
    return [float(value) for value in vector_text.split(",")]