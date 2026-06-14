import { IsString, MinLength } from "class-validator";

export class CreateResumeDto {
    @IsString()
    @MinLength(2)
    title!: string;

    @IsString()
    @MinLength(20)
    rawText!: string;
}