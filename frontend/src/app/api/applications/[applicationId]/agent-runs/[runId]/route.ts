import { proxyToBackend } from '../proxy';

type RouteContext = { params: Promise<{ applicationId: string; runId: string }> };

export async function GET(_request: Request, context: RouteContext) {
  const { applicationId, runId } = await context.params;
  return proxyToBackend(
    `/applications/${encodeURIComponent(applicationId)}/agent-runs/${encodeURIComponent(runId)}`,
    'GET',
  );
}
