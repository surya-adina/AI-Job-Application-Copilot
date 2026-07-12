import { apiGet, apiPost } from './client';
import type { ResumeReviewReport } from '@/types/resume-review';

export async function getResumeReviewForApplication(
  applicationId: string,
  token: string,
) {
  return apiGet<ResumeReviewReport>(
    `/applications/${applicationId}/resume-review`,
    { token },
  );
}

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