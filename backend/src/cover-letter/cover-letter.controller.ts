import { Controller, Get, Param, Post, Req, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CoverLetterService } from './cover-letter.service';

type AuthenticatedRequest = {
  user: {
    userId: string;
    email: string;
  };
};

@Controller('applications/:applicationId/cover-letter')
@UseGuards(JwtAuthGuard)
export class CoverLetterController {
  constructor(private readonly coverLetterService: CoverLetterService) {}

  @Get()
  getForApplication(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.coverLetterService.getForApplication(
      applicationId,
      req.user.userId,
    );
  }

  @Post()
  createForApplication(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.coverLetterService.createForApplication(
      applicationId,
      req.user.userId,
    );
  }
}