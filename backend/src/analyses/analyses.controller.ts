import { Controller, Get, Param, Post, Req, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { AnalysesService } from './analyses.service';

@Controller('analyses')
@UseGuards(JwtAuthGuard)
export class AnalysesController {
  constructor(private analysesService: AnalysesService) {}

  @Post('applications/:applicationId')
  createForApplication(
    @Req() req: any,
    @Param('applicationId') applicationId: string,
  ) {
    return this.analysesService.createForApplication(
      req.user.userId,
      applicationId,
    );
  }

  @Get(':id')
  findOne(@Req() req: any, @Param('id') id: string) {
    return this.analysesService.findOne(req.user.userId, id);
  }
}