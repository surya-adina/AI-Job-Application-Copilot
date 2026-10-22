-- CreateTable
CREATE TABLE "ResumeChunk" (
    "id" TEXT NOT NULL,
    "resumeId" TEXT NOT NULL,
    "chunkIndex" INTEGER NOT NULL,
    "text" TEXT NOT NULL,
    "startOffset" INTEGER NOT NULL,
    "endOffset" INTEGER NOT NULL,
    "contentHash" TEXT NOT NULL,
    "embedding" vector(1536),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ResumeChunk_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ResumeChunk_resumeId_idx" ON "ResumeChunk"("resumeId");

-- CreateIndex
CREATE UNIQUE INDEX "ResumeChunk_resumeId_chunkIndex_key" ON "ResumeChunk"("resumeId", "chunkIndex");

-- AddForeignKey
ALTER TABLE "ResumeChunk" ADD CONSTRAINT "ResumeChunk_resumeId_fkey" FOREIGN KEY ("resumeId") REFERENCES "Resume"("id") ON DELETE CASCADE ON UPDATE CASCADE;
