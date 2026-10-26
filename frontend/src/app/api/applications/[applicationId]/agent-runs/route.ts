import { proxyToBackend } from './proxy';

type RouteContext = { params: Promise<{ applicationId: string }> };

export async function GET(request: Request, context: RouteContext) {
  const { applicationId } = await context.params;
  const task = new URL(request.url).searchParams.get('task');
  const query = task ? `?task=${encodeURIComponent(task)}` : '';
  return proxyToBackend(`/applications/${encodeURIComponent(applicationId)}/agent-runs${query}`, 'GET');
}

export async function POST(request: Request, context: RouteContext) {
  const { applicationId } = await context.params;
  const body = await request.json().catch(() => ({}));
  return proxyToBackend(`/applications/${encodeURIComponent(applicationId)}/agent-runs`, 'POST', body);
}
