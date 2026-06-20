import { ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { AiGatewayService } from '../ai-gateway/ai-gateway.service';

@Injectable()
export class AnalysesService {
  constructor(
    private prisma: PrismaService,
    private aiGateway: AiGatewayService,
  ) {}

  async createForApplication(userId: string, applicationId: string) {
    const application = await this.prisma.application.findFirst({
      where: {
        id: applicationId,
        userId,
      },
      include: {
        job: true,
        resume: true,
        analysis: true,
      },
    });

    if (!application) {
      throw new NotFoundException('Application not found');
    }

    if (!application.resume) {
      throw new ConflictException('Application must have a resume before analysis');
    }

    if (application.analysis) {
      throw new ConflictException('Analysis already exists for this application');
    }

    let matchReport;

    try {
      matchReport = await this.aiGateway.analyze({
        resume_text: application.resume.rawText,
        job_description: application.job.jdText,
      });
    } catch (error) {
      await this.prisma.aiRun.create({
        data: {
          userId,
          endpoint: '/analyze',
          model: 'unknown',
          promptVersion: 'unknown',
          tokensIn: 0,
          tokensOut: 0,
          totalTokens: 0,
          latencyMs: 0,
          retries: 0,
          status: 'FAILED',
          errorType:
          error instanceof Error && 'code' in error && error.code === 'ECONNREFUSED'
            ? 'AI_SERVICE_UNAVAILABLE'
            : error instanceof Error
              ? error.name
              : 'UNKNOWN_ERROR',
        },
      });

      throw error;
    }

    await this.prisma.aiRun.create({
      data: {
        userId,
        endpoint: matchReport.metadata.endpoint,
        model: matchReport.metadata.model,
        promptVersion: matchReport.metadata.prompt_version,
        tokensIn: matchReport.metadata.tokens_in,
        tokensOut: matchReport.metadata.tokens_out,
        totalTokens: matchReport.metadata.total_tokens,
        latencyMs: matchReport.metadata.latency_ms,
        retries: 0,
        status: matchReport.metadata.status,
        estimatedCostUsd: matchReport.metadata.estimated_cost_usd ?? null,
      },
    });

    return this.prisma.analysis.create({
      data: {
        applicationId,
        score: matchReport.analysis.score,
        matchedSkills: matchReport.analysis.matched_skills,
        missingSkills: matchReport.analysis.missing_skills,
        strengths: matchReport.analysis.strengths.join('\n'),
        weaknesses: matchReport.analysis.weaknesses.join('\n'),
        suggestions: {
          recommendations: matchReport.analysis.recommendations,
        },
      },
    });
  }

  async findOne(userId: string, id: string) {
    const analysis = await this.prisma.analysis.findFirst({
      where: {
        id,
        application: {
          userId,
        },
      },
      include: {
        application: {
          include: {
            job: true,
            resume: true,
          },
        },
      },
    });

    if (!analysis) {
      throw new NotFoundException('Analysis not found');
    }

    return analysis;
  }
}