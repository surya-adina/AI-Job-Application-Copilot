import { Injectable } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';

type AnalyzeRequest = {
  resume_text: string;
  job_description: string;
};

type AnalyzeResponse = {
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
};

@Injectable()
export class AiGatewayService {
  private readonly aiServiceUrl = 'http://localhost:8000';

  constructor(private httpService: HttpService) {}

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