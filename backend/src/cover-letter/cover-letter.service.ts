import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { AiGatewayService } from '../ai-gateway/ai-gateway.service';

@Injectable()
export class CoverLetterService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly aiGateway: AiGatewayService,
  ) {}

  async getForApplication(applicationId: string, userId: string) {
    const savedCoverLetter = await this.prisma.coverLetter.findFirst({
      where: {
        applicationId,
        application: {
          userId,
        },
      },
    });

    if (!savedCoverLetter) {
      throw new NotFoundException('Cover letter not found');
    }

    return {
      id: savedCoverLetter.id,
      content: savedCoverLetter.content,
      metadata: null,
      createdAt: savedCoverLetter.createdAt,
      updatedAt: savedCoverLetter.updatedAt,
    };
  }

  async createForApplication(applicationId: string, userId: string) {
    const application = await this.prisma.application.findFirst({
      where: {
        id: applicationId,
        userId,
      },
      include: {
        resume: true,
        job: true,
        coverLetter: true,
      },
    });

    if (!application) {
      throw new NotFoundException('Application not found');
    }

    if (!application.resume || !application.job) {
      throw new NotFoundException('Application is missing resume or job');
    }

    const result = await this.aiGateway.createCoverLetter({
      resumeText: application.resume.rawText,
      jobDescription: application.job.jdText,
    });

    const savedCoverLetter = await this.prisma.coverLetter.upsert({
      where: {
        applicationId,
      },
      update: {
        content: result.content,
      },
      create: {
        applicationId,
        content: result.content,
      },
    });

    return {
      id: savedCoverLetter.id,
      content: savedCoverLetter.content,
      metadata: result.metadata,
      createdAt: savedCoverLetter.createdAt,
      updatedAt: savedCoverLetter.updatedAt,
    };
  }
}