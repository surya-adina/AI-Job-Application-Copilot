export type AgentRunStatus = 'RUNNING' | 'AWAITING_REVIEW' | 'COMPLETED' | 'REJECTED' | 'FAILED';

export type AgentLlmCall = {
  endpoint: string;
  model: string;
  promptVersion: string;
  tokensIn: number;
  tokensOut: number;
  latencyMs: number;
  retries: number;
  status: string;
  errorType: string | null;
  estimatedCostUsd: string | null;
};

export type AgentStep = {
  id: string;
  index: number;
  node: string;
  status: string;
  latencyMs: number;
  detail: Record<string, unknown> | null;
  error: { type: string; message: string } | null;
  aiRuns: AgentLlmCall[];
};

export type ClaimVerdict = {
  text: string;
  supported: boolean;
  reasons: string[];
};

export type ReviewParagraph = {
  key: string;
  text: string;
  passed: boolean;
  claims: ClaimVerdict[];
};

export type AgentReview = {
  letter: string;
  paragraphs: ReviewParagraph[];
  unresolved: Record<string, string[]>;
  revisions: Record<string, number>;
};

export type AgentRun = {
  id: string;
  task: string;
  status: AgentRunStatus;
  instructions: string | null;
  review: AgentReview | null;
  decision: { action: string; edited: boolean } | null;
  finalText: string | null;
  error: { type?: string; message: string } | null;
  steps: AgentStep[];
  totals: { llmCalls: number; costUsd: number; latencyMs: number };
  createdAt: string;
  updatedAt: string;
};

export type AgentRunSummary = Pick<AgentRun, 'id' | 'task' | 'status' | 'createdAt' | 'updatedAt'>;

export type AgentDecision = { action: 'approve' | 'reject' } | { action: 'edit'; text: string };
