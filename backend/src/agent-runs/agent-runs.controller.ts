import { Body, Controller, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { AgentRunsService } from './agent-runs.service';
import { AgentDecisionDto } from './dto/agent-decision.dto';
import { AGENT_TASKS, AgentTask, StartAgentRunDto } from './dto/start-agent-run.dto';

type AuthenticatedRequest = {
  user: {
    userId: string;
    email: string;
  };
};

@Controller('applications/:applicationId/agent-runs')
@UseGuards(JwtAuthGuard)
export class AgentRunsController {
  constructor(private readonly agentRuns: AgentRunsService) {}

  @Post()
  start(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
    @Body() dto: StartAgentRunDto,
  ) {
    return this.agentRuns.start(req.user.userId, applicationId, dto.task, dto.instructions);
  }

  @Get()
  list(
    @Param('applicationId') applicationId: string,
    @Req() req: AuthenticatedRequest,
    @Query('task') task?: string,
  ) {
    const filter = AGENT_TASKS.includes(task as AgentTask) ? (task as AgentTask) : undefined;
    return this.agentRuns.list(req.user.userId, applicationId, filter);
  }

  @Get(':runId')
  findOne(
    @Param('applicationId') applicationId: string,
    @Param('runId') runId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.agentRuns.findOne(req.user.userId, applicationId, runId);
  }

  @Post(':runId/decision')
  decide(
    @Param('applicationId') applicationId: string,
    @Param('runId') runId: string,
    @Req() req: AuthenticatedRequest,
    @Body() dto: AgentDecisionDto,
  ) {
    return this.agentRuns.decide(req.user.userId, applicationId, runId, dto);
  }
}
