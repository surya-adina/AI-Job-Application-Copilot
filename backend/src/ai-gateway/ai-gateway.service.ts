import { Injectable } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';

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

type AiRunMetadata = {
  endpoint: string;
  model: string;
  prompt_version: string;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  status: string;
  error_type?: string | null;
  estimated_cost_usd?: number | null;
};

export type AnalyzeResponse = {
  analysis: AnalysisPayload;
  metadata: AiRunMetadata;
};


@Injectable()
export class AiGatewayService {
  private readonly aiServiceUrl = 'http://localhost:8000';

  constructor(private httpService: HttpService) {}
  async createResumeReview(input: {
    resumeText: string;
    jobDescription: string;
    analysis: unknown;
    evidence: unknown;
  }) {
    const response = await this.httpService.axiosRef.post(
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
  }) {
    const response = await this.httpService.axiosRef.post(
      `${this.aiServiceUrl}/cover-letter`,
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
}