import { apiGet, apiPost } from './client';
import type { InterviewPrepReport } from '@/types/interview-prep';

export async function getInterviewPrepForApplication(
  applicationId: string,
  token: string,
) {
  return apiGet<InterviewPrepReport>(
    `/applications/${applicationId}/interview-prep`,
    { token },
  );
}

export async function createInterviewPrepForApplication(
  applicationId: string,
  token: string,
) {
  return apiPost<InterviewPrepReport>(
    `/applications/${applicationId}/interview-prep`,
    undefined,
    { token },
  );
}