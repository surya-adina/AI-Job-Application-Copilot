import { apiPost } from './client';

export type AnalysisReport = {
  id: string;
  applicationId: string;
  score: number;
  matchedSkills: string[];
  missingSkills: string[];
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  createdAt: string;
};

export async function createAnalysisForApplication(
  applicationId: string,
  token: string,
) {
  return apiPost<AnalysisReport>(
    `/analyses/applications/${applicationId}`,
    undefined,
    { token },
  );
}