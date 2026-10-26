import { IsIn, IsOptional, IsString, MaxLength } from 'class-validator';

export const AGENT_TASKS = ['cover_letter', 'resume_tailoring'] as const;
export type AgentTask = (typeof AGENT_TASKS)[number];

export class StartAgentRunDto {
  @IsOptional()
  @IsIn(AGENT_TASKS)
  task?: AgentTask;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  instructions?: string;
}
