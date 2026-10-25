export type AgentRunStatus = 'RUNNING' | 'AWAITING_REVIEW' | 'COMPLETED' | 'REJECTED' | 'FAILED';

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
};

export type AgentRun = {
  id: string;
  task: string;
  status: AgentRunStatus;
  instructions: string | null;
  review: AgentReview | null;
  decision: { action: string; edited: boolean } | null;
  finalText: string | null;
  createdAt: string;
  updatedAt: string;
};

export type AgentRunSummary = Pick<AgentRun, 'id' | 'task' | 'status' | 'createdAt' | 'updatedAt'>;

export type AgentDecision = { action: 'approve' | 'reject' } | { action: 'edit'; text: string };
