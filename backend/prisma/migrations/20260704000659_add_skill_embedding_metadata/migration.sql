-- CreateTable
CREATE TABLE "SkillEmbedding" (
    "id" TEXT NOT NULL,
    "skill" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SkillEmbedding_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "SkillEmbedding_skill_key" ON "SkillEmbedding"("skill");

ALTER TABLE "SkillEmbedding"
ADD COLUMN "embedding" vector(1536);

CREATE INDEX "SkillEmbedding_embedding_idx"
ON "SkillEmbedding"
USING ivfflat ("embedding" vector_cosine_ops)
WITH (lists = 100);