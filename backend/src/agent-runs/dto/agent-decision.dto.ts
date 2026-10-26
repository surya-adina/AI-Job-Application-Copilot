import { Type } from 'class-transformer';
import {
  ArrayMaxSize,
  IsArray,
  IsIn,
  IsInt,
  IsOptional,
  IsString,
  MaxLength,
  MinLength,
  ValidateIf,
  ValidateNested,
} from 'class-validator';

export class TailorChoiceDto {
  @IsInt()
  unitId!: number;

  @IsIn(['accept', 'edit', 'keep'])
  choice!: 'accept' | 'edit' | 'keep';

  @ValidateIf((dto: TailorChoiceDto) => dto.choice === 'edit')
  @IsString()
  @MinLength(1)
  @MaxLength(1500)
  text?: string;
}

/**
 * Cover letter runs take approve | edit | reject. Resume tailoring runs take
 * save (with a name for the new resume and a choice per rewritten line) or discard.
 */
export class AgentDecisionDto {
  @IsIn(['approve', 'edit', 'reject', 'save', 'discard'])
  action!: 'approve' | 'edit' | 'reject' | 'save' | 'discard';

  @ValidateIf((dto: AgentDecisionDto) => dto.action === 'edit')
  @IsString()
  @MinLength(1)
  @MaxLength(10000)
  text?: string;

  @ValidateIf((dto: AgentDecisionDto) => dto.action === 'save')
  @IsString()
  @MinLength(1)
  @MaxLength(200)
  title?: string;

  @IsOptional()
  @IsArray()
  @ArrayMaxSize(20)
  @ValidateNested({ each: true })
  @Type(() => TailorChoiceDto)
  items?: TailorChoiceDto[];
}
