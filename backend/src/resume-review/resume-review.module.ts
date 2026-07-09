import { Module } from '@nestjs/common';
import { AiGatewayModule } from '../ai-gateway/ai-gateway.module';
import { ResumeReviewController } from './resume-review.controller';
import { ResumeReviewService } from './resume-review.service';

@Module({
  imports: [AiGatewayModule],
  controllers: [ResumeReviewController],
  providers: [ResumeReviewService],
})
export class ResumeReviewModule {}