import { Controller, Get, Param, Post, Req, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { InterviewPrepService } from './interview-prep.service';

type AuthenticatedRequest = {
  user: {
    sub: string;
    email: string;
  };
};

@Controller('applications/:applicationId/interview-prep')
@UseGuards(JwtAuthGuard)
export class InterviewPrepController {
  constructor(private readonly interviewPrepService: InterviewPrepService) {}

  @Get()
  getForApplication(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.interviewPrepService.getForApplication(
      applicationId,
      req.user.sub,
    );
  }

  @Post()
  createForApplication(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.interviewPrepService.createForApplication(
      applicationId,
      req.user.sub,
    );
  }
}