export type ApplicationWorkspace = {
  application: {
    id: string;
    company: string;
    role: string;
    status: string;
    notes: string | null;
    createdAt: string;
    resumeTitle: string;
  };

  analysis: {
    id: string;
    score: number;
    matchedSkills: string[];
    missingSkills: string[];
    strengths: string;
    weaknesses: string;
    suggestions: {
      recommendations: string[];
    };
    createdAt: string;
  } | null;

  progress: {
    resumeUploaded: boolean;
    analysisComplete: boolean;
    resumeReviewComplete: boolean;
    coverLetterComplete: boolean;
    interviewPrepComplete: boolean;
  };
};