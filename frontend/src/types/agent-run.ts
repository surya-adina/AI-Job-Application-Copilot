export type AgentTask = 'cover_letter' | 'resume_tailoring';

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

export type CoverLetterReview = {
  letter: string;
  paragraphs: ReviewParagraph[];
  unresolved: Record<string, string[]>;
};

export type TailorItem = {
  unitId: number;
  original: string;
  rewritten: string;
  unchanged: boolean;
  passed: boolean;
  problems: string[];
};

export type TailoringReview = {
  items: TailorItem[];
  missingSkills: string[];
};

export type AgentRun = {
  id: string;
  task: AgentTask;
  status: AgentRunStatus;
  instructions: string | null;
  review: CoverLetterReview | TailoringReview | null;
  decision: {
    action: string;
    edited?: boolean;
    resumeId?: string;
    title?: string;
    accepted?: number;
  } | null;
  finalText: string | null;
  suggestedTitle: string | null;
  createdAt: string;
  updatedAt: string;
};

export type AgentRunSummary = Pick<AgentRun, 'id' | 'task' | 'status' | 'createdAt' | 'updatedAt'>;

export type TailorChoice = { unitId: number; choice: 'accept' | 'edit' | 'keep'; text?: string };

export type AgentDecision =
  | { action: 'approve' | 'reject' }
  | { action: 'edit'; text: string }
  | { action: 'save'; title: string; items: TailorChoice[] }
  | { action: 'discard' };
