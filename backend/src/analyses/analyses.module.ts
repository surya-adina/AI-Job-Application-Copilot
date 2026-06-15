import { Module } from '@nestjs/common';
import { AnalysesController } from './analyses.controller';
import { AnalysesService } from './analyses.service';
import { AiGatewayModule } from 'src/ai-gateway/ai-gateway.module';

@Module({
  imports: [AiGatewayModule],
  controllers: [AnalysesController],
  providers: [AnalysesService],
})
export class AnalysesModule {}