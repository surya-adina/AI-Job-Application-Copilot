import { apiPost } from './client';
import type { ResumeReviewReport } from '@/types/resume-review';

export async function createResumeReviewForApplication(
  applicationId: string,
  token: string,
) {
  return apiPost<ResumeReviewReport>(
    `/applications/${applicationId}/resume-review`,
    undefined,
    { token },
  );
}