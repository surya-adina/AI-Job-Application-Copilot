import type { InterviewPrepReport } from '@/types/interview-prep';

export async function getInterviewPrepForApplication(
  applicationId: string,
): Promise<InterviewPrepReport> {
  const response = await fetch(
    `/api/applications/${applicationId}/interview-prep`,
    {
      method: 'GET',
      credentials: 'include',
    },
  );

  if (!response.ok) {
    throw new Error('Failed to fetch interview prep');
  }

  return response.json();
}

export async function createInterviewPrepForApplication(
  applicationId: string,
): Promise<InterviewPrepReport> {
  const response = await fetch(
    `/api/applications/${applicationId}/interview-prep`,
    {
      method: 'POST',
      credentials: 'include',
    },
  );

  if (!response.ok) {
    throw new Error('Failed to create interview prep');
  }

  return response.json();
}