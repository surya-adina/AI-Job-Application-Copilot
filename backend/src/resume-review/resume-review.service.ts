import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { AiGatewayService } from '../ai-gateway/ai-gateway.service';

@Injectable()
export class ResumeReviewService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly aiGateway: AiGatewayService,
  ) {}

  async createForApplication(applicationId: string, userId: string) {
    const application = await this.prisma.application.findFirst({
      where: {
        id: applicationId,
        userId,
      },
      include: {
        resume: true,
        job: true,
        analysis: true,
      },
    });

    if (!application) {
      throw new NotFoundException('Application not found');
    }

    if (!application.resume || !application.job) {
      throw new NotFoundException('Application is missing resume or job');
    }

    if (!application.analysis) {
      throw new NotFoundException('Run analysis before requesting resume review');
    }

    return this.aiGateway.createResumeReview({
      resumeText: application.resume.rawText,
      jobDescription: application.job.jdText,
      analysis: application.analysis,
      evidence: {},
    });
  }
}