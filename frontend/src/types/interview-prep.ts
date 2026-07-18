export type InterviewQuestion = {
  question: string;
  why_it_matters: string;
  suggested_focus: string;
};

export type InterviewPrepReport = {
  id: string;
  technical_questions: InterviewQuestion[];
  behavioral_questions: InterviewQuestion[];
  project_questions: InterviewQuestion[];
  preparation_tips: string[];
  metadata: {
    endpoint: string;
    model: string;
    prompt_version: string;
    latency_ms: number;
    status: 'SUCCESS' | 'FAILED';
  } | null;
  createdAt: string;
  updatedAt: string;
};