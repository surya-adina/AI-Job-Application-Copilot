import { Controller, Param, Post, Req, UseGuards, Get } from '@nestjs/common';
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
  constructor(private readonly resumeReviewService: ResumeReviewService) {}

  @Get()
  getForApplication(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.resumeReviewService.getForApplication(
      applicationId,
      req.user.sub,
    );
  }

  @Post()
  createForApplication(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.resumeReviewService.createForApplication(
      applicationId,
      req.user.sub,
    );
  }
}