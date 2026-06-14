import { IsOptional, IsString, IsUrl, MinLength } from 'class-validator';

export class CreateJobDto {
  @IsOptional()
  @IsString()
  company?: string;

  @IsString()
  @MinLength(2)
  title!: string;

  @IsString()
  @MinLength(50)
  jdText!: string;

  @IsOptional()
  @IsUrl()
  sourceUrl?: string;
}