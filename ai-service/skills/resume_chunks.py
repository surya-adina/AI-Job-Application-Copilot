"""Resume evidence search: split a resume into chunks, embed them once, and
find the chunks closest to a query with pgvector.

Chunks are stored in ResumeChunk (one row per chunk, deleted with the resume).
Re-indexing only happens when the resume text changes (contentHash).
"""

import hashlib
import re
from dataclasses import dataclass

import psycopg

from skills.embedding_client import embed
from skills.embedding_store import to_vector_literal

MIN_WORDS = 4
MAX_CHUNK_CHARS = 400
BULLET_PREFIX = re.compile(r"^[\s\-–—•*▪●◦·]+")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass
class Chunk:
    index: int
    text: str
    start: int
    end: int


@dataclass
class ChunkMatch:
    index: int
    text: str
    start: int
    end: int
    similarity: float


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _pieces(line: str, line_start: int) -> list[tuple[str, int]]:
    """Split an over-long line into sentences, keeping offsets."""
    if len(line) <= MAX_CHUNK_CHARS:
        return [(line, line_start)]

    pieces = []
    cursor = 0
    for part in SENTENCE_SPLIT.split(line):
        position = line.find(part, cursor)
        pieces.append((part, line_start + position))
        cursor = position + len(part)
    return pieces


def chunk_resume(text: str) -> list[Chunk]:
    """One chunk per bullet or line (sentences for long lines). Headings and
    short fragments (fewer than MIN_WORDS words) are skipped."""
    chunks = []
    offset = 0

    for raw_line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(raw_line)

        stripped = BULLET_PREFIX.sub("", raw_line.rstrip("\r\n"))
        content = stripped.strip()
        if not content:
            continue

        start = line_start + raw_line.find(content)
        for piece, piece_start in _pieces(content, start):
            piece = piece.strip()
            if len(piece.split()) < MIN_WORDS:
                continue
            chunks.append(Chunk(index=len(chunks), text=piece, start=piece_start, end=piece_start + len(piece)))

    return chunks


def index_resume(connection: psycopg.Connection, resume_id: str, resume_text: str) -> int:
    """Store chunk embeddings for a resume unless they are already current. Returns the chunk count."""
    digest = content_hash(resume_text)

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT "contentHash", count(*) FROM "ResumeChunk" WHERE "resumeId" = %s GROUP BY "contentHash"',
            (resume_id,),
        )
        rows = cursor.fetchall()

    if len(rows) == 1 and rows[0][0] == digest:
        return rows[0][1]

    chunks = chunk_resume(resume_text)
    vectors = embed([chunk.text for chunk in chunks])

    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "ResumeChunk" WHERE "resumeId" = %s', (resume_id,))
            cursor.executemany(
                """
                INSERT INTO "ResumeChunk"
                    ("id", "resumeId", "chunkIndex", "text", "startOffset", "endOffset", "contentHash", "embedding")
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s::vector)
                """,
                [
                    (resume_id, chunk.index, chunk.text, chunk.start, chunk.end, digest, to_vector_literal(vector))
                    for chunk, vector in zip(chunks, vectors)
                ],
            )

    return len(chunks)


SEARCH_SQL = """
WITH resume_chunks AS MATERIALIZED (
    SELECT "chunkIndex", "text", "startOffset", "endOffset", "embedding"
    FROM "ResumeChunk"
    WHERE "resumeId" = %s
)
SELECT "chunkIndex", "text", "startOffset", "endOffset", 1 - ("embedding" <=> %s::vector) AS similarity
FROM resume_chunks
ORDER BY "embedding" <=> %s::vector
LIMIT %s
"""


def search_resume(connection: psycopg.Connection, resume_id: str, query: str, k: int = 5) -> list[ChunkMatch]:
    query_vector = to_vector_literal(embed([query])[0])

    with connection.cursor() as cursor:
        cursor.execute(SEARCH_SQL, (resume_id, query_vector, query_vector, k))
        return [
            ChunkMatch(index=index, text=text, start=start, end=end, similarity=round(float(similarity), 4))
            for index, text, start, end, similarity in cursor.fetchall()
        ]
