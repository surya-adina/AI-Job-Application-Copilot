import { Module } from '@nestjs/common';
import { AiGatewayModule } from '../ai-gateway/ai-gateway.module';
import { PrismaService } from '../../prisma/prisma.service';
import { CoverLetterController } from './cover-letter.controller';
import { CoverLetterService } from './cover-letter.service';

@Module({
  imports: [AiGatewayModule],
  controllers: [CoverLetterController],
  providers: [CoverLetterService, PrismaService],
})
export class CoverLetterModule {}