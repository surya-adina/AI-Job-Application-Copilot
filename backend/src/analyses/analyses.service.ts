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

    const aiResult = await this.aiGateway.analyze({
      resume_text: application.resume.rawText,
      job_description: application.job.jdText,
    });

    await this.prisma.aiRun.create({
      data: {
        userId,
        endpoint: aiResult.metadata.endpoint,
        model: aiResult.metadata.model,
        promptVersion: aiResult.metadata.prompt_version,
        tokensIn: aiResult.metadata.tokens_in,
        tokensOut: aiResult.metadata.tokens_out,
        totalTokens: aiResult.metadata.total_tokens,
        latencyMs: aiResult.metadata.latency_ms,
        retries: 0,
        status: aiResult.metadata.status,
      },
    });

    return this.prisma.analysis.create({
      data: {
        applicationId,
        score: aiResult.analysis.score,
        matchedSkills: aiResult.analysis.matched_skills,
        missingSkills: aiResult.analysis.missing_skills,
        strengths: aiResult.analysis.strengths.join('\n'),
        weaknesses: aiResult.analysis.weaknesses.join('\n'),
        suggestions: {
          recommendations: aiResult.analysis.recommendations,
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