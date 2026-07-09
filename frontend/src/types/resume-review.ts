export type ResumeSuggestion = {
  rank?: number;
  priority?: 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  target_section?: string;
  why: string;
  evidence: string[];
  action: string;
};

export type ResumeReviewReport = {
  review: {
    summary: string;
    suggestions: ResumeSuggestion[];
    growth_areas: string[];
    warnings: string[];
  };
  metadata: {
    endpoint: string;
    model: string;
    prompt_version: string;
    latency_ms: number;
    tokens_in: number;
    tokens_out: number;
    total_tokens: number;
    status: 'SUCCESS' | 'FAILED';
    error_type: string | null;
  };
};