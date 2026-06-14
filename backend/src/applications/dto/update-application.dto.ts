import { IsEnum, IsOptional, IsString, IsUUID } from 'class-validator';
import { ApplicationStatus } from '@prisma/client';

export class UpdateApplicationDto {
  @IsOptional()
  @IsEnum(ApplicationStatus)
  status?: ApplicationStatus;

  @IsOptional()
  @IsUUID()
  resumeId?: string;

  @IsOptional()
  @IsString()
  notes?: string;
}