import { Controller, Param, Post, Req, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { ResumeReviewService } from './resume-review.service';

type AuthenticatedRequest = {
  user: {
    sub: string;
    email: string;
  };
};

@Controller('applications/:applicationId/resume-review')
@UseGuards(JwtAuthGuard)
export class ResumeReviewController {
  constructor(private readonly resumeReview: ResumeReviewService) {}

  @Post()
  createForApplication(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.resumeReview.createForApplication(applicationId, req.user.sub);
  }
}