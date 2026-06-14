import { Injectable, NotFoundException } from "@nestjs/common";
import { PrismaService } from "prisma/prisma.service";
import { CreateResumeDto } from "./dto/create-resume.dto";

@Injectable()
export class ResumesService {
    constructor(private prisma: PrismaService) {}

    create(userId: string, dto: CreateResumeDto) {
        return this.prisma.resume.create({
            data: {
                userId,
                title: dto.title,
                rawText: dto.rawText,
            },
        });
    }
    findAll(userId: string) {
        return this.prisma.resume.findMany({
            where: { userId },
            orderBy: {createdAt: 'desc'},
        });
    }
    async findOne(userId: string, id: string) {
        const resume = await this.prisma.resume.findFirst({
            where: {
                id,
                userId,
            },
        });
        if(!resume) {
            throw new NotFoundException('Resume not found');
        }
        return resume;
    }
    async remove(userId: string, id: string) {
    const resume = await this.prisma.resume.findFirst({
      where: {
        id,
        userId,
      },
    });

    if (!resume) {
      throw new NotFoundException('Resume not found');
    }

    return this.prisma.resume.delete({
      where: { id },
    });
  }
}