import { Injectable, NotFoundException } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import { AiGatewayService } from '../ai-gateway/ai-gateway.service';

@Injectable()
export class InterviewPrepService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly aiGateway: AiGatewayService,
  ) {}

  async getForApplication(applicationId: string, userId: string) {
    const savedPrep = await this.prisma.interviewPrep.findFirst({
      where: {
        applicationId,
        application: {
          userId,
        },
      },
    });

    if (!savedPrep) {
      throw new NotFoundException('Interview prep not found');
    }

    return {
      id: savedPrep.id,
      technical_questions: savedPrep.technicalQuestions,
      behavioral_questions: savedPrep.behavioralQuestions,
      project_questions: savedPrep.projectQuestions,
      preparation_tips: savedPrep.preparationTips,
      metadata: null,
      createdAt: savedPrep.createdAt,
      updatedAt: savedPrep.updatedAt,
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
        interviewPrep: true,
      },
    });

    if (!application) {
      throw new NotFoundException('Application not found');
    }

    if (!application.resume || !application.job) {
      throw new NotFoundException('Application is missing resume or job');
    }

    const result = await this.aiGateway.createInterviewPrep({
      resumeText: application.resume.rawText,
      jobDescription: application.job.jdText,
    });

    const savedPrep = await this.prisma.interviewPrep.upsert({
      where: {
        applicationId,
      },
      update: {
        technicalQuestions:
          result.technical_questions as Prisma.InputJsonValue,
        behavioralQuestions:
          result.behavioral_questions as Prisma.InputJsonValue,
        projectQuestions: result.project_questions as Prisma.InputJsonValue,
        preparationTips: result.preparation_tips,
      },
      create: {
        applicationId,
        technicalQuestions:
          result.technical_questions as Prisma.InputJsonValue,
        behavioralQuestions:
          result.behavioral_questions as Prisma.InputJsonValue,
        projectQuestions: result.project_questions as Prisma.InputJsonValue,
        preparationTips: result.preparation_tips,
      },
    });

    return {
      id: savedPrep.id,
      technical_questions: savedPrep.technicalQuestions,
      behavioral_questions: savedPrep.behavioralQuestions,
      project_questions: savedPrep.projectQuestions,
      preparation_tips: savedPrep.preparationTips,
      metadata: result.metadata,
      createdAt: savedPrep.createdAt,
      updatedAt: savedPrep.updatedAt,
    };
  }
}