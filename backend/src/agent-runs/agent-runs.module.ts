import { Module } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { AiGatewayModule } from '../ai-gateway/ai-gateway.module';
import { AgentRunsController } from './agent-runs.controller';
import { AgentRunsService } from './agent-runs.service';

@Module({
  imports: [AiGatewayModule],
  controllers: [AgentRunsController],
  providers: [AgentRunsService, PrismaService],
})
export class AgentRunsModule {}
