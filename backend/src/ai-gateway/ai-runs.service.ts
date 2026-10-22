import { Injectable, Logger } from '@nestjs/common';
import { isAxiosError } from 'axios';
import { PrismaService } from '../../prisma/prisma.service';

/** Metadata block every ai-service endpoint returns (see ai-service/llm/client.py RunMetadata). */
export type AiRunMetadata = {
  endpoint: string;
  model: string;
  prompt_version: string;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  retries: number;
  status: 'SUCCESS' | 'FAILED';
  error_type?: string | null;
  estimated_cost_usd?: number | null;
};

@Injectable()
export class AiRunsService {
  private readonly logger = new Logger(AiRunsService.name);

  constructor(private prisma: PrismaService) {}

  async record(userId: string, metadata: AiRunMetadata) {
    try {
      await this.prisma.aiRun.create({
        data: {
          userId,
          endpoint: metadata.endpoint,
          model: metadata.model,
          promptVersion: metadata.prompt_version,
          tokensIn: metadata.tokens_in ?? 0,
          tokensOut: metadata.tokens_out ?? 0,
          totalTokens: metadata.total_tokens ?? 0,
          latencyMs: metadata.latency_ms ?? 0,
          retries: metadata.retries ?? 0,
          status: metadata.status,
          errorType: metadata.error_type ?? null,
          estimatedCostUsd: metadata.estimated_cost_usd ?? null,
        },
      });
    } catch (error) {
      // Observability must never break the user-facing request.
      this.logger.warn(`Failed to record AiRun for ${metadata.endpoint}: ${String(error)}`);
    }
  }

  /**
   * Record a failed call. When the ai-service answered with an error, its
   * detail.metadata carries the real model, tokens, retries and error type;
   * otherwise (service down, network error) we log what we know.
   */
  async recordFailure(userId: string, endpoint: string, error: unknown) {
    const serviceMetadata = isAxiosError(error)
      ? (error.response?.data as { detail?: { metadata?: AiRunMetadata } } | undefined)?.detail?.metadata
      : undefined;

    if (serviceMetadata) {
      await this.record(userId, { ...serviceMetadata, status: 'FAILED' });
      return;
    }

    let errorType = 'UNKNOWN_ERROR';
    if (isAxiosError(error)) {
      if (error.code === 'ECONNREFUSED') {
        errorType = 'AI_SERVICE_UNAVAILABLE';
      } else if (error.response) {
        errorType = `HTTP_${error.response.status}`;
      } else {
        errorType = error.code ?? 'NETWORK_ERROR';
      }
    } else if (error instanceof Error) {
      errorType = error.name;
    }

    await this.record(userId, {
      endpoint,
      model: 'unknown',
      prompt_version: 'unknown',
      latency_ms: 0,
      tokens_in: 0,
      tokens_out: 0,
      total_tokens: 0,
      retries: 0,
      status: 'FAILED',
      error_type: errorType,
    });
  }

  /** Call the ai-service and record the run either way. */
  async track<T extends { metadata: AiRunMetadata }>(
    userId: string,
    endpoint: string,
    call: () => Promise<T>,
  ): Promise<T> {
    let result: T;
    try {
      result = await call();
    } catch (error) {
      await this.recordFailure(userId, endpoint, error);
      throw error;
    }
    await this.record(userId, result.metadata);
    return result;
  }
}
