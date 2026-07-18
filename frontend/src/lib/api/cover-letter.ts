import type { CoverLetterReport } from '@/types/cover-letter';

export async function getCoverLetterForApplication(
  applicationId: string,
): Promise<CoverLetterReport> {
  const response = await fetch(
    `/api/applications/${applicationId}/cover-letter`,
    {
      method: 'GET',
      credentials: 'include',
    },
  );

  if (!response.ok) {
    throw new Error('Failed to fetch cover letter');
  }

  return response.json();
}

export async function createCoverLetterForApplication(
  applicationId: string,
): Promise<CoverLetterReport> {
  const response = await fetch(
    `/api/applications/${applicationId}/cover-letter`,
    {
      method: 'POST',
      credentials: 'include',
    },
  );

  if (!response.ok) {
    throw new Error('Failed to create cover letter');
  }

  return response.json();
}