import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { AiGatewayService } from './ai-gateway.service';
import { AiRunsService } from './ai-runs.service';

@Module({
  imports: [HttpModule],
  providers: [AiGatewayService, AiRunsService],
  exports: [AiGatewayService, AiRunsService],
})
export class AiGatewayModule {}