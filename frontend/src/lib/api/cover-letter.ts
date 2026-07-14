import { apiGet, apiPost } from './client';
import type { CoverLetterReport } from '@/types/cover-letter';

export async function getCoverLetterForApplication(
  applicationId: string,
  token: string,
) {
  return apiGet<CoverLetterReport>(
    `/applications/${applicationId}/cover-letter`,
    { token },
  );
}

export async function createCoverLetterForApplication(
  applicationId: string,
  token: string,
) {
  return apiPost<CoverLetterReport>(
    `/applications/${applicationId}/cover-letter`,
    undefined,
    { token },
  );
}