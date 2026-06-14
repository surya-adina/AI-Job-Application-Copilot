import { Body, Controller, Delete, Get, Param, Post, Req, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CreateResumeDto } from './dto/create-resume.dto';
import { ResumesService } from './resumes.service';

@Controller('resumes')
@UseGuards(JwtAuthGuard)
export class ResumesController {
  constructor(private resumesService: ResumesService) {}

  @Post()
  create(@Req() req: any, @Body() dto: CreateResumeDto) {
    return this.resumesService.create(req.user.userId, dto);
  }

  @Get()
  findAll(@Req() req: any) {
    return this.resumesService.findAll(req.user.userId);
  }

  @Get(':id')
  findOne(@Req() req: any, @Param('id') id: string) {
    return this.resumesService.findOne(req.user.userId, id);
  }

  @Delete(':id')
  remove(@Req() req: any, @Param('id') id: string) {
    return this.resumesService.remove(req.user.userId, id);
  }
}