import { Injectable } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import type { AiRunMetadata } from './ai-runs.service';

type AnalyzeRequest = {
  resume_text: string;
  job_description: string;
};

type AnalysisPayload = {
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
};

export type SkillDecision = {
  skill: string;
  priority: 'required' | 'preferred';
  present: boolean;
  basis: string;
  evidence: string | null;
};

export type SkillEvidence = {
  mode: string;
  resume_skills: string[];
  required_skills: string[];
  preferred_skills: string[];
  missing_required_skills: string[];
  missing_preferred_skills: string[];
  semantic_matches: { job_skill: string; resume_skill: string; similarity: number }[];
  skills: SkillDecision[];
};

export type AnalyzeResponse = {
  analysis: AnalysisPayload;
  metadata: AiRunMetadata;
  evidence: SkillEvidence;
  runs: AiRunMetadata[];
};

export type CoverLetterResponse = {
  content: string;
  paragraphs: { text: string; supporting_resume_quotes: string[] }[];
  grounding: {
    quotes_checked: number;
    unsupported_quotes: string[];
    placeholders: string[];
  };
  metadata: AiRunMetadata;
};

type InterviewQuestion = {
  question: string;
  why_it_matters: string;
  suggested_focus: string;
};

export type InterviewPrepResponse = {
  technical_questions: InterviewQuestion[];
  behavioral_questions: InterviewQuestion[];
  project_questions: InterviewQuestion[];
  preparation_tips: string[];
  metadata: AiRunMetadata;
};

export type ResumeReviewResponse = {
  review: {
    summary: string;
    suggestions: {
      priority: 'HIGH' | 'MEDIUM' | 'LOW';
      title: string;
      target_section: string;
      why: string;
      evidence: string[];
      action: string;
      unsupported_skills: string[];
    }[];
    growth_areas: string[];
    warnings: string[];
  };
  metadata: AiRunMetadata;
};

export type AgentStepPayload = {
  node: string;
  status: string;
  latency_ms: number;
  runs: AiRunMetadata[];
  detail: unknown;
  error?: { type: string; message: string } | null;
};

export type AgentRunResponse = {
  thread_id: string;
  status: 'awaiting_review' | 'completed' | 'rejected' | 'failed';
  steps: AgentStepPayload[];
  review: Record<string, unknown> | null;
  final_text: string | null;
  error: { type: string; message: string } | null;
};

@Injectable()
export class AiGatewayService {
  private readonly aiServiceUrl = process.env.AI_SERVICE_URL ?? 'http://localhost:8000';

  constructor(private httpService: HttpService) {
    // The ai-service rejects requests without the shared token. Read it per
    // request: backend/.env is loaded by Prisma Client, not at module init.
    this.httpService.axiosRef.interceptors.request.use((config) => {
      config.headers.set('X-Service-Token', process.env.AI_SERVICE_TOKEN ?? '');
      return config;
    });
  }
  async createResumeReview(input: {
    resumeText: string;
    jobDescription: string;
    analysis: unknown;
    evidence: unknown;
  }): Promise<ResumeReviewResponse> {
    const response = await this.httpService.axiosRef.post<ResumeReviewResponse>(
      `${this.aiServiceUrl}/resume-review`,
      {
        resume_text: input.resumeText,
        job_description: input.jobDescription,
        analysis: input.analysis,
        evidence: input.evidence,
        prompt_version: 'resume_review_v1',
      },
    );

    return response.data;
  }

  async createCoverLetter(payload: {
    resumeText: string;
    jobDescription: string;
  }): Promise<CoverLetterResponse> {
    const response = await this.httpService.axiosRef.post<CoverLetterResponse>(
      `${this.aiServiceUrl}/cover-letter`,
      {
        resume_text: payload.resumeText,
        job_description: payload.jobDescription,
      },
    );

    return response.data;
  }

  async createInterviewPrep(payload: {
    resumeText: string;
    jobDescription: string;
  }): Promise<InterviewPrepResponse> {
    const response = await this.httpService.axiosRef.post<InterviewPrepResponse>(
      `${this.aiServiceUrl}/interview-prep`,
      {
        resume_text: payload.resumeText,
        job_description: payload.jobDescription,
      },
    );

    return response.data;
  }

  async analyze(input: AnalyzeRequest): Promise<AnalyzeResponse> {
    const response = await firstValueFrom(
      this.httpService.post<AnalyzeResponse>(
        `${this.aiServiceUrl}/analyze`,
        input,
      ),
    );

    return response.data;
  }

  async startAgentRun(input: {
    threadId: string;
    task: 'cover_letter' | 'resume_tailoring';
    resumeId: string;
    resumeText: string;
    jobDescription: string;
    instructions: string;
  }): Promise<AgentRunResponse> {
    const response = await this.httpService.axiosRef.post<AgentRunResponse>(
      `${this.aiServiceUrl}/agent/runs`,
      {
        thread_id: input.threadId,
        task: input.task,
        resume_id: input.resumeId,
        resume_text: input.resumeText,
        job_description: input.jobDescription,
        instructions: input.instructions,
      },
    );
    return response.data;
  }

  async resumeAgentRun(
    threadId: string,
    decision: {
      task: 'cover_letter' | 'resume_tailoring';
      action: 'approve' | 'edit' | 'reject' | 'save' | 'discard';
      text?: string;
      title?: string;
      items?: { unit_id: number; choice: 'accept' | 'edit' | 'keep'; text?: string }[];
    },
  ): Promise<AgentRunResponse> {
    const response = await this.httpService.axiosRef.post<AgentRunResponse>(
      `${this.aiServiceUrl}/agent/runs/${encodeURIComponent(threadId)}/resume`,
      decision,
    );
    return response.data;
  }
}
