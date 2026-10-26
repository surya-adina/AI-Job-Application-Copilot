import { BadRequestException, ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import { AgentRunStatus, Prisma } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import { AgentRunResponse, AiGatewayService } from '../ai-gateway/ai-gateway.service';
import { AiRunsService } from '../ai-gateway/ai-runs.service';
import { AgentDecisionDto } from './dto/agent-decision.dto';
import { AgentTask } from './dto/start-agent-run.dto';

const STATUS: Record<AgentRunResponse['status'], AgentRunStatus> = {
  awaiting_review: AgentRunStatus.AWAITING_REVIEW,
  completed: AgentRunStatus.COMPLETED,
  rejected: AgentRunStatus.REJECTED,
  failed: AgentRunStatus.FAILED,
};

type CoverLetterReview = {
  letter: string;
  paragraphs: { key: string; text: string; passed: boolean; claims: { text: string; supported: boolean; reasons: string[] }[] }[];
  unresolved: Record<string, string[]>;
};

type TailoringReview = {
  items: { unit_id: number; original: string; rewritten: string; unchanged: boolean; passed: boolean; problems: string[] }[];
  missing_skills: string[];
};

const ACTIONS: Record<AgentTask, AgentDecisionDto['action'][]> = {
  cover_letter: ['approve', 'edit', 'reject'],
  resume_tailoring: ['save', 'discard'],
};

/** Keep only what the review screen needs from the agent's review payload. */
function toUserReview(task: string, review: Prisma.JsonValue | null) {
  if (!review || typeof review !== 'object' || Array.isArray(review)) {
    return null;
  }
  if (task === 'resume_tailoring') {
    const payload = review as unknown as TailoringReview;
    return {
      items: payload.items.map((item) => ({
        unitId: item.unit_id,
        original: item.original,
        rewritten: item.rewritten,
        unchanged: item.unchanged,
        passed: item.passed,
        problems: item.problems,
      })),
      missingSkills: payload.missing_skills,
    };
  }
  const payload = review as unknown as CoverLetterReview;
  return {
    letter: payload.letter,
    paragraphs: payload.paragraphs.map((paragraph) => ({
      key: paragraph.key,
      text: paragraph.text,
      passed: paragraph.passed,
      claims: paragraph.claims.map(({ text, supported, reasons }) => ({ text, supported, reasons })),
    })),
    unresolved: payload.unresolved,
  };
}

const ACTIVE: AgentRunStatus[] = [AgentRunStatus.RUNNING, AgentRunStatus.AWAITING_REVIEW];

@Injectable()
export class AgentRunsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly aiGateway: AiGatewayService,
    private readonly aiRuns: AiRunsService,
  ) {}

  async start(userId: string, applicationId: string, task: AgentTask = 'cover_letter', instructions = '') {
    const application = await this.prisma.application.findFirst({
      where: { id: applicationId, userId },
      include: { job: true, resume: true },
    });

    if (!application) {
      throw new NotFoundException('Application not found');
    }
    if (!application.resume) {
      throw new ConflictException('Application must have a resume before running the agent');
    }

    const active = await this.prisma.agentRun.findFirst({
      where: { applicationId, task, status: { in: ACTIVE } },
    });
    if (active) {
      throw new ConflictException('Finish reviewing the current draft before starting a new one');
    }

    const run = await this.prisma.agentRun.create({
      data: { userId, applicationId, task, instructions: instructions || null },
    });

    const resume = application.resume;
    let response: AgentRunResponse;
    try {
      response = await this.aiGateway.startAgentRun({
        threadId: run.id,
        task,
        resumeId: resume.id,
        resumeText: resume.rawText,
        jobDescription: application.job.jdText,
        instructions,
      });
    } catch (error) {
      await this.prisma.agentRun.update({
        where: { id: run.id },
        data: {
          status: AgentRunStatus.FAILED,
          error: { message: error instanceof Error ? error.message : 'AI service request failed' },
        },
      });
      await this.aiRuns.recordFailure(userId, '/agent/runs', error);
      throw error;
    }

    await this.applyResponse(userId, run.id, response);
    return this.findOne(userId, applicationId, run.id);
  }

  async decide(userId: string, applicationId: string, runId: string, dto: AgentDecisionDto) {
    const run = await this.prisma.agentRun.findFirst({
      where: { id: runId, applicationId, userId },
    });

    if (!run) {
      throw new NotFoundException('Agent run not found');
    }
    if (run.status !== AgentRunStatus.AWAITING_REVIEW) {
      throw new ConflictException('This agent run is not waiting for review');
    }
    const task = run.task as AgentTask;
    if (!ACTIONS[task]?.includes(dto.action)) {
      throw new BadRequestException(`"${dto.action}" is not a valid decision for this draft`);
    }

    // If this request fails, the run stays AWAITING_REVIEW and can be decided again.
    const response = await this.aiGateway.resumeAgentRun(run.id, {
      task,
      action: dto.action,
      text: dto.action === 'edit' ? dto.text : undefined,
      title: dto.action === 'save' ? dto.title?.trim() : undefined,
      items: (dto.items ?? []).map((item) => ({ unit_id: item.unitId, choice: item.choice, text: item.text })),
    });

    await this.applyResponse(userId, run.id, response);
    const completed = response.status === 'completed' && response.final_text;
    let decision: Prisma.InputJsonValue = { action: dto.action, edited: dto.action === 'edit' };

    if (completed && task === 'cover_letter') {
      await this.prisma.coverLetter.upsert({
        where: { applicationId },
        update: { content: response.final_text! },
        create: { applicationId, content: response.final_text! },
      });
    }

    if (completed && task === 'resume_tailoring') {
      // A new resume; the one the application uses is left unchanged.
      const resume = await this.prisma.resume.create({
        data: { userId, title: dto.title!.trim(), rawText: response.final_text! },
      });
      const choices = (dto.items ?? []).map((item) => item.choice);
      decision = {
        action: dto.action,
        resumeId: resume.id,
        title: resume.title,
        accepted: choices.filter((choice) => choice === 'accept').length,
        edited: choices.filter((choice) => choice === 'edit').length,
      };
    }

    await this.prisma.agentRun.update({ where: { id: run.id }, data: { decision } });
    return this.findOne(userId, applicationId, run.id);
  }

  async list(userId: string, applicationId: string, task?: AgentTask) {
    return this.prisma.agentRun.findMany({
      where: { applicationId, userId, ...(task ? { task } : {}) },
      orderBy: { createdAt: 'desc' },
      select: { id: true, task: true, status: true, createdAt: true, updatedAt: true },
    });
  }

  /**
   * The user-facing view of a run: status, the draft under review and the
   * outcome. Steps, model calls, tokens and cost stay in AgentStep/AiRun for
   * evaluation and are not sent to the browser.
   */
  async findOne(userId: string, applicationId: string, runId: string) {
    const run = await this.prisma.agentRun.findFirst({
      where: { id: runId, applicationId, userId },
      select: {
        id: true,
        task: true,
        status: true,
        instructions: true,
        review: true,
        decision: true,
        finalText: true,
        createdAt: true,
        updatedAt: true,
      },
    });

    if (!run) {
      throw new NotFoundException('Agent run not found');
    }

    let suggestedTitle: string | null = null;
    if (run.task === 'resume_tailoring') {
      const application = await this.prisma.application.findFirst({
        where: { id: applicationId, userId },
        include: { job: true, resume: true },
      });
      const job = application?.job;
      const target = job ? `${job.title}${job.company ? ` at ${job.company}` : ''}` : 'this job';
      suggestedTitle = `${application?.resume?.title ?? 'Resume'} – tailored for ${target}`.slice(0, 200);
    }

    return { ...run, review: toUserReview(run.task, run.review), suggestedTitle };
  }

  /** Store steps the backend has not seen yet (one AiRun row per LLM call) and the run's new state. */
  private async applyResponse(userId: string, runId: string, response: AgentRunResponse) {
    const known = await this.prisma.agentStep.findMany({
      where: { agentRunId: runId },
      select: { index: true },
    });
    const knownIndexes = new Set(known.map((step) => step.index));

    for (const [index, step] of response.steps.entries()) {
      if (knownIndexes.has(index)) {
        continue;
      }

      const saved = await this.prisma.agentStep.create({
        data: {
          agentRunId: runId,
          index,
          node: step.node,
          status: step.status,
          latencyMs: step.latency_ms,
          detail: (step.detail ?? undefined) as Prisma.InputJsonValue | undefined,
          error: (step.error ?? undefined) as Prisma.InputJsonValue | undefined,
        },
      });

      for (const call of step.runs) {
        await this.aiRuns.record(userId, call, { agentRunId: runId, agentStepId: saved.id });
      }
    }

    await this.prisma.agentRun.update({
      where: { id: runId },
      data: {
        status: STATUS[response.status],
        review: response.review ? (response.review as Prisma.InputJsonValue) : Prisma.DbNull,
        finalText: response.final_text,
        error: response.error ? (response.error as Prisma.InputJsonValue) : Prisma.DbNull,
      },
    });
  }
}
