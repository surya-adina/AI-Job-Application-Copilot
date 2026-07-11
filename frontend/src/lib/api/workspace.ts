import { apiGet } from './client';
import type { ApplicationWorkspace } from '@/types/workspace';

export async function getWorkspace(
  applicationId: string,
  token: string,
) {
  return apiGet<ApplicationWorkspace>(
    `/applications/${applicationId}/workspace`,
    { token },
  );
}