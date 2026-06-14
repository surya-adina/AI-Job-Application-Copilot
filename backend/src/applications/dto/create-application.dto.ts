import { IsOptional, IsString, IsUUID } from 'class-validator';

export class CreateApplicationDto {
  @IsUUID()
  jobId!: string;

  @IsOptional()
  @IsUUID()
  resumeId?: string;

  @IsOptional()
  @IsString()
  notes?: string;
}