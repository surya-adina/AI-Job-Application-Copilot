import { IsOptional, IsString, MaxLength } from 'class-validator';

export class StartAgentRunDto {
  @IsOptional()
  @IsString()
  @MaxLength(1000)
  instructions?: string;
}
