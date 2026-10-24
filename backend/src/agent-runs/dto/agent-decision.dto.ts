import { IsIn, IsString, MaxLength, MinLength, ValidateIf } from 'class-validator';

export class AgentDecisionDto {
  @IsIn(['approve', 'edit', 'reject'])
  action!: 'approve' | 'edit' | 'reject';

  @ValidateIf((dto: AgentDecisionDto) => dto.action === 'edit')
  @IsString()
  @MinLength(1)
  @MaxLength(10000)
  text?: string;
}
