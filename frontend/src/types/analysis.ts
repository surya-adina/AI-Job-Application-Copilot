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