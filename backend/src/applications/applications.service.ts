import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { CreateApplicationDto } from './dto/create-application.dto';
import { UpdateApplicationDto } from './dto/update-application.dto';

@Injectable()
export class ApplicationsService {
  constructor(private prisma: PrismaService) {}

  async create(userId: string, dto: CreateApplicationDto) {
    const job = await this.prisma.job.findFirst({
      where: {
        id: dto.jobId,
        userId,
      },
    });

    if (!job) {
      throw new NotFoundException('Job not found');
    }

    if (dto.resumeId) {
      const resume = await this.prisma.resume.findFirst({
        where: {
          id: dto.resumeId,
          userId,
        },
      });

      if (!resume) {
        throw new NotFoundException('Resume not found');
      }
    }

    return this.prisma.application.create({
      data: {
        userId,
        jobId: dto.jobId,
        resumeId: dto.resumeId,
        notes: dto.notes,
      },
      include: {
        job: true,
        resume: true,
      },
    });
  }

  findAll(userId: string) {
    return this.prisma.application.findMany({
      where: { userId },
      include: {
        job: true,
        resume: true,
        analysis: true,
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOne(userId: string, id: string) {
    const application = await this.prisma.application.findFirst({
      where: {
        id,
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

    return application;
  }

  async update(userId: string, id: string, dto: UpdateApplicationDto) {
    const application = await this.prisma.application.findFirst({
      where: {
        id,
        userId,
      },
    });

    if (!application) {
      throw new NotFoundException('Application not found');
    }

    if (dto.resumeId) {
      const resume = await this.prisma.resume.findFirst({
        where: {
          id: dto.resumeId,
          userId,
        },
      });

      if (!resume) {
        throw new NotFoundException('Resume not found');
      }
    }

    return this.prisma.application.update({
      where: { id },
      data: {
        status: dto.status,
        resumeId: dto.resumeId,
        notes: dto.notes,
      },
      include: {
        job: true,
        resume: true,
        analysis: true,
      },
    });
  }

  async remove(userId: string, id: string) {
    const application = await this.prisma.application.findFirst({
      where: {
        id,
        userId,
      },
    });

    if (!application) {
      throw new NotFoundException('Application not found');
    }

    return this.prisma.application.delete({
      where: { id },
    });
  }

  async getWorkspace(applicationId: string, userId: string) {
    const application = await this.prisma.application.findFirst({
      where: {
        id: applicationId,
        userId,
      },
      include: {
        resume: true,
        job: true,
        analysis: true,
        resumeReview: true,
        coverLetter: true,
        interviewPrep: true,
      },
    });

    if (!application) {
      throw new NotFoundException('Application not found');
    }

    if (!application.resume || !application.job) {
      throw new NotFoundException('Application is missing resume or job');
    }


    const analysisComplete = Boolean(application.analysis);

    return {
      application: {
        id: application.id,
        status: application.status,
        notes: application.notes,
        createdAt: application.createdAt,
        company: application.job.company,
        role: application.job.title,
        resumeTitle: application.resume.title,
      },
      analysis: application.analysis
        ? {
            id: application.analysis.id,
            score: application.analysis.score,
            matchedSkills: application.analysis.matchedSkills,
            missingSkills: application.analysis.missingSkills,
            strengths: application.analysis.strengths,
            weaknesses: application.analysis.weaknesses,
            suggestions: application.analysis.suggestions,
            createdAt: application.analysis.createdAt,
          }
        : null,
      progress: {
        resumeUploaded: true,
        analysisComplete,
        resumeReviewComplete: Boolean(application.resumeReview),
        coverLetterComplete: Boolean(application.coverLetter),
        interviewPrepComplete: Boolean(application.interviewPrep),
      },
    };
  }
}