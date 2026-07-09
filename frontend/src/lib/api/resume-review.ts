import { apiPost } from './client';
import type { ResumeReviewReport } from '@/types/resume-review';

type CreateResumeReviewInput = {
  resumeText: string;
  jobDescription: string;
  analysis: unknown;
  evidence: unknown;
};

export async function createResumeReview(
  input: CreateResumeReviewInput,
  token: string,
) {
  return apiPost<ResumeReviewReport>(
    '/resume-review',
    {
      resume_text: input.resumeText,
      job_description: input.jobDescription,
      analysis: input.analysis,
      evidence: input.evidence,
      prompt_version: 'resume_review_v1',
    },
    { token },
  );
}