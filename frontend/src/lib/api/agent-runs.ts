import type { AgentDecision, AgentRun, AgentRunSummary } from '@/types/agent-run';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/applications/${path}`, {
    credentials: 'include',
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(data?.message ?? 'Request failed');
  }
  return data as T;
}

export function listAgentRuns(applicationId: string) {
  return request<AgentRunSummary[]>(`${applicationId}/agent-runs`);
}

export function getAgentRun(applicationId: string, runId: string) {
  return request<AgentRun>(`${applicationId}/agent-runs/${runId}`);
}

export function startAgentRun(applicationId: string, instructions: string) {
  return request<AgentRun>(`${applicationId}/agent-runs`, {
    method: 'POST',
    body: JSON.stringify(instructions ? { instructions } : {}),
  });
}

export function decideAgentRun(applicationId: string, runId: string, decision: AgentDecision) {
  return request<AgentRun>(`${applicationId}/agent-runs/${runId}/decision`, {
    method: 'POST',
    body: JSON.stringify(decision),
  });
}
