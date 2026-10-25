import { ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import { AgentRunStatus, Prisma } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import { AgentRunResponse, AiGatewayService } from '../ai-gateway/ai-gateway.service';
import { AiRunsService } from '../ai-gateway/ai-runs.service';
import { AgentDecisionDto } from './dto/agent-decision.dto';

const STATUS: Record<AgentRunResponse['status'], AgentRunStatus> = {
  awaiting_review: AgentRunStatus.AWAITING_REVIEW,
  completed: AgentRunStatus.COMPLETED,
  rejected: AgentRunStatus.REJECTED,
  failed: AgentRunStatus.FAILED,
};

type ReviewPayload = {
  letter: string;
  paragraphs: { key: string; text: string; passed: boolean; claims: { text: string; supported: boolean; reasons: string[] }[] }[];
  unresolved: Record<string, string[]>;
};

/** Keep only what the review screen needs from the agent's review payload. */
function toUserReview(review: Prisma.JsonValue | null) {
  if (!review || typeof review !== 'object' || Array.isArray(review)) {
    return null;
  }
  const payload = review as unknown as ReviewPayload;
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

  async start(userId: string, applicationId: string, instructions = '') {
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
      where: { applicationId, status: { in: ACTIVE } },
    });
    if (active) {
      throw new ConflictException('This application already has an agent run in progress');
    }

    const run = await this.prisma.agentRun.create({
      data: { userId, applicationId, task: 'cover_letter', instructions: instructions || null },
    });

    const resume = application.resume;
    let response: AgentRunResponse;
    try {
      response = await this.aiGateway.startAgentRun({
        threadId: run.id,
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

    // If this request fails, the run stays AWAITING_REVIEW and can be decided again.
    const response = await this.aiGateway.resumeAgentRun(run.id, {
      action: dto.action,
      text: dto.action === 'edit' ? dto.text : undefined,
    });

    await this.applyResponse(userId, run.id, response);
    await this.prisma.agentRun.update({
      where: { id: run.id },
      data: { decision: { action: dto.action, edited: dto.action === 'edit' } },
    });

    if (response.status === 'completed' && response.final_text) {
      await this.prisma.coverLetter.upsert({
        where: { applicationId },
        update: { content: response.final_text },
        create: { applicationId, content: response.final_text },
      });
    }

    return this.findOne(userId, applicationId, run.id);
  }

  async list(userId: string, applicationId: string) {
    return this.prisma.agentRun.findMany({
      where: { applicationId, userId },
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

    return { ...run, review: toUserReview(run.review) };
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
