import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import * as mammoth from 'mammoth';
import { PrismaService } from '../../prisma/prisma.service';
import { CreateResumeDto } from './dto/create-resume.dto';

const { PDFParse } = require('pdf-parse');

@Injectable()
export class ResumesService {
  constructor(private prisma: PrismaService) {}

  async create(userId: string, dto: CreateResumeDto) {
    return this.prisma.resume.create({
      data: {
        userId,
        title: dto.title,
        rawText: dto.rawText,
      },
    });
  }

  async upload(userId: string, file: Express.Multer.File, title?: string) {
    if (!file) {
      throw new BadRequestException('Resume file is required');
    }

    const rawText = await this.extractText(file);

    if (rawText.trim().length < 20) {
      throw new BadRequestException(
        'Could not extract enough text from this resume. Try another file or paste the resume text manually.',
      );
    }

    return this.prisma.resume.create({
      data: {
        userId,
        title: title?.trim() || this.buildTitleFromFileName(file.originalname),
        rawText: rawText.trim(),
      },
    });
  }

  async findAll(userId: string) {
    return this.prisma.resume.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOne(userId: string, id: string) {
    const resume = await this.prisma.resume.findFirst({
      where: {
        id,
        userId,
      },
    });

    if (!resume) {
      throw new NotFoundException('Resume not found');
    }

    return resume;
  }

  async remove(userId: string, id: string) {
    await this.findOne(userId, id);

    return this.prisma.resume.delete({
      where: { id },
    });
  }

  private async extractText(file: Express.Multer.File) {
    const mimeType = file.mimetype;
    const fileName = file.originalname.toLowerCase();

    if (mimeType === 'application/pdf' || fileName.endsWith('.pdf')) {
        const parser = new PDFParse({ data: file.buffer });

        try {
            const parsed = await parser.getText();
            return parsed.text;
        } finally {
            await parser.destroy();
        }
        }

    if (
      mimeType ===
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
      fileName.endsWith('.docx')
    ) {
      const parsed = await mammoth.extractRawText({
        buffer: file.buffer,
      });
      return parsed.value;
    }

    if (mimeType === 'text/plain' || fileName.endsWith('.txt')) {
      return file.buffer.toString('utf-8');
    }

    throw new BadRequestException(
      'Unsupported file type. Upload a PDF, DOCX, or TXT resume.',
    );
  }

  private buildTitleFromFileName(fileName: string) {
    return fileName
      .replace(/\.[^/.]+$/, '')
      .replace(/[-_]/g, ' ')
      .trim();
  }
}