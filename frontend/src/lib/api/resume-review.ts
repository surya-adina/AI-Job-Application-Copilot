import type { ResumeReviewReport } from '@/types/resume-review';

export async function getResumeReviewForApplication(
  applicationId: string,
): Promise<ResumeReviewReport> {
  const response = await fetch(
    `/api/applications/${applicationId}/resume-review`,
    {
      method: 'GET',
      credentials: 'include',
    },
  );

  if (!response.ok) {
    throw new Error('Failed to fetch resume review');
  }

  return response.json();
}

export async function createResumeReviewForApplication(
  applicationId: string,
): Promise<ResumeReviewReport> {
  const response = await fetch(
    `/api/applications/${applicationId}/resume-review`,
    {
      method: 'POST',
      credentials: 'include',
    },
  );

  if (!response.ok) {
    throw new Error('Failed to create resume review');
  }

  return response.json();
}