export type CoverLetterReport = {
  id: string;
  content: string;
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