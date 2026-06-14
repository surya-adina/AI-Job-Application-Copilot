import { ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class AnalysesService {
  constructor(private prisma: PrismaService) {}

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

    return this.prisma.analysis.create({
      data: {
        applicationId,
        score: 78,
        matchedSkills: ['React', 'Node.js', 'PostgreSQL', 'Prisma', 'NestJS'],
        missingSkills: ['AWS', 'Docker', 'OpenTelemetry'],
        strengths:
          'Strong full-stack foundation with backend API, Prisma, and PostgreSQL experience.',
        weaknesses:
          'Limited visible production deployment, cloud infrastructure, and observability evidence.',
        suggestions: {
          resumeBullets: [
            'Highlight production-style backend architecture using NestJS, Prisma, and PostgreSQL.',
            'Add measurable AI infrastructure work such as eval metrics, latency tracking, and token cost logging.',
          ],
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