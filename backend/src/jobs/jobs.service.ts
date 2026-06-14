import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { CreateJobDto } from './dto/create-job.dto';

@Injectable()
export class JobsService {
  constructor(private prisma: PrismaService) {}

  create(userId: string, dto: CreateJobDto) {
    return this.prisma.job.create({
      data: {
        userId,
        company: dto.company,
        title: dto.title,
        jdText: dto.jdText,
        sourceUrl: dto.sourceUrl,
      },
    });
  }

  findAll(userId: string) {
    return this.prisma.job.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOne(userId: string, id: string) {
    const job = await this.prisma.job.findFirst({
      where: {
        id,
        userId,
      },
    });

    if (!job) {
      throw new NotFoundException('Job not found');
    }

    return job;
  }

  async remove(userId: string, id: string) {
    const job = await this.prisma.job.findFirst({
      where: {
        id,
        userId,
      },
    });

    if (!job) {
      throw new NotFoundException('Job not found');
    }

    return this.prisma.job.delete({
      where: { id },
    });
  }
}