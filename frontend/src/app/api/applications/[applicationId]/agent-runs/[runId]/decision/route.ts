import { proxyToBackend } from '../../proxy';

type RouteContext = { params: Promise<{ applicationId: string; runId: string }> };

export async function POST(request: Request, context: RouteContext) {
  const { applicationId, runId } = await context.params;
  const body = await request.json().catch(() => ({}));
  return proxyToBackend(
    `/applications/${encodeURIComponent(applicationId)}/agent-runs/${encodeURIComponent(runId)}/decision`,
    'POST',
    body,
  );
}
