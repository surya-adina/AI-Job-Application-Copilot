import { proxyToBackend } from './proxy';

type RouteContext = { params: Promise<{ applicationId: string }> };

export async function GET(_request: Request, context: RouteContext) {
  const { applicationId } = await context.params;
  return proxyToBackend(`/applications/${encodeURIComponent(applicationId)}/agent-runs`, 'GET');
}

export async function POST(request: Request, context: RouteContext) {
  const { applicationId } = await context.params;
  const body = await request.json().catch(() => ({}));
  return proxyToBackend(`/applications/${encodeURIComponent(applicationId)}/agent-runs`, 'POST', body);
}
