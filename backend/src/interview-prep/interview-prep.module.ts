import { Module } from '@nestjs/common';
import { AiGatewayModule } from '../ai-gateway/ai-gateway.module';
import { PrismaService } from '../../prisma/prisma.service';
import { InterviewPrepController } from './interview-prep.controller';
import { InterviewPrepService } from './interview-prep.service';

@Module({
  imports: [AiGatewayModule],
  controllers: [InterviewPrepController],
  providers: [InterviewPrepService, PrismaService],
})
export class InterviewPrepModule {}