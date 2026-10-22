-- Replace the ivfflat index with HNSW. ivfflat with lists = 100 needs thousands
-- of rows to build useful clusters; on a small table most lists are empty and
-- recall drops. HNSW has no training step and works at any table size.
-- An earlier generated migration dropped the ivfflat index, so drop defensively.
DROP INDEX IF EXISTS "SkillEmbedding_embedding_idx";

CREATE INDEX "SkillEmbedding_embedding_idx"
ON "SkillEmbedding"
USING hnsw ("embedding" vector_cosine_ops);
