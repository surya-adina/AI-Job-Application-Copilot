"""Skill similarity computed in Postgres with pgvector's cosine distance (<=>).

`best_candidate_matches` takes (skill, candidate) pairs and returns, for each
skill, its closest candidate and the cosine similarity (1 - distance). The
per-request candidate sets are small, so this is an exact search; the HNSW
index on SkillEmbedding.embedding serves nearest-neighbour lookups over the
whole table.
"""

import psycopg

from skills.embedding_client import embed, ensure_skill_embeddings
from skills.embedding_store import get_connection, to_vector_literal

BEST_MATCH_SQL = """
WITH pairs AS (
    SELECT DISTINCT skill, candidate
    FROM unnest(%s::text[], %s::text[]) AS p(skill, candidate)
    WHERE skill <> candidate
)
SELECT DISTINCT ON (pairs.skill)
    pairs.skill,
    pairs.candidate,
    1 - (s.embedding <=> c.embedding) AS similarity
FROM pairs
JOIN "SkillEmbedding" s ON s.skill = pairs.skill
JOIN "SkillEmbedding" c ON c.skill = pairs.candidate
ORDER BY pairs.skill, s.embedding <=> c.embedding
"""

TEXT_SIMILARITY_SQL = """
SELECT q.position, 1 - (s.embedding <=> q.query_vector::vector) AS similarity
FROM unnest(%s::text[], %s::text[]) WITH ORDINALITY AS q(skill, query_vector, position)
JOIN "SkillEmbedding" s ON s.skill = q.skill
"""


class PgVectorSimilarity:
    """Similarity backed by SkillEmbedding. One instance per request."""

    def __init__(self, connection: psycopg.Connection | None = None):
        self.connection = connection or get_connection()

    def close(self) -> None:
        self.connection.close()

    def best_candidate_matches(self, pairs: list[tuple[str, str]]) -> dict[str, tuple[str, float]]:
        pairs = [(skill, candidate) for skill, candidate in pairs if skill != candidate]
        if not pairs:
            return {}

        ensure_skill_embeddings(self.connection, [name for pair in pairs for name in pair])
        skills, candidates = zip(*pairs)

        with self.connection.cursor() as cursor:
            cursor.execute(BEST_MATCH_SQL, (list(skills), list(candidates)))
            return {skill: (candidate, float(similarity)) for skill, candidate, similarity in cursor.fetchall()}

    def text_similarity(self, skill_texts: list[tuple[str, str]]) -> dict[tuple[str, str], float]:
        """Similarity between a stored skill and a free-text phrase (not stored)."""
        skill_texts = [(skill, text) for skill, text in skill_texts if text.strip()]
        if not skill_texts:
            return {}

        ensure_skill_embeddings(self.connection, [skill for skill, _ in skill_texts])
        vectors = [to_vector_literal(vector) for vector in embed([text for _, text in skill_texts])]

        with self.connection.cursor() as cursor:
            cursor.execute(TEXT_SIMILARITY_SQL, ([skill for skill, _ in skill_texts], vectors))
            rows = cursor.fetchall()

        # ORDINALITY is 1-based and ties each row back to its input pair.
        return {skill_texts[position - 1]: float(similarity) for position, similarity in rows}


def find_semantic_matches(
    resume_skills: list[str],
    job_skills: list[str],
    threshold: float = 0.78,
    similarity: PgVectorSimilarity | None = None,
) -> list[dict]:
    """For each job skill, the closest resume skill when similarity >= threshold."""
    owned = similarity is None
    similarity = similarity or PgVectorSimilarity()

    try:
        best = similarity.best_candidate_matches(
            [(job_skill, resume_skill) for job_skill in job_skills for resume_skill in resume_skills]
        )
    finally:
        if owned:
            similarity.close()

    return [
        {"job_skill": job_skill, "resume_skill": candidate, "similarity": round(score, 3)}
        for job_skill, (candidate, score) in best.items()
        if score >= threshold
    ]
