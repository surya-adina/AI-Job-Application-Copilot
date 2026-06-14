import { Body, Controller, Delete, Get, Param, Post, Req, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CreateJobDto } from './dto/create-job.dto';
import { JobsService } from './jobs.service';

@Controller('jobs')
@UseGuards(JwtAuthGuard)
export class JobsController {
  constructor(private jobsService: JobsService) {}

  @Post()
  create(@Req() req: any, @Body() dto: CreateJobDto) {
    return this.jobsService.create(req.user.userId, dto);
  }

  @Get()
  findAll(@Req() req: any) {
    return this.jobsService.findAll(req.user.userId);
  }

  @Get(':id')
  findOne(@Req() req: any, @Param('id') id: string) {
    return this.jobsService.findOne(req.user.userId, id);
  }

  @Delete(':id')
  remove(@Req() req: any, @Param('id') id: string) {
    return this.jobsService.remove(req.user.userId, id);
  }
}