import { ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { AiGatewayService } from '../ai-gateway/ai-gateway.service';
import { AiRunsService } from '../ai-gateway/ai-runs.service';

@Injectable()
export class AnalysesService {
  constructor(
    private prisma: PrismaService,
    private aiGateway: AiGatewayService,
    private readonly aiRuns: AiRunsService,
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

    const resumeText = application.resume.rawText;
    const matchReport = await this.aiRuns.track(userId, '/analyze', () =>
      this.aiGateway.analyze({
        resume_text: resumeText,
        job_description: application.job.jdText,
      }),
    );

    const analysisData = {
      score: matchReport.analysis.score,
      matchedSkills: matchReport.analysis.matched_skills,
      missingSkills: matchReport.analysis.missing_skills,
      strengths: matchReport.analysis.strengths.join('\n'),
      weaknesses: matchReport.analysis.weaknesses.join('\n'),
      suggestions: {
        recommendations: matchReport.analysis.recommendations,
      },
    };

    return this.prisma.analysis.upsert({
      where: {
        applicationId,
      },
      update: analysisData,
      create: {
        applicationId,
        ...analysisData,
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