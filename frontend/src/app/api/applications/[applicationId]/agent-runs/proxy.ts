import { NextResponse } from 'next/server';
import { getAuthToken } from '@/lib/auth/server';

const API_BASE = process.env.BACKEND_API_URL ?? 'http://localhost:4000';

/** Forward a request to the backend with the user's token from the HTTP-only cookie. */
export async function proxyToBackend(path: string, method: 'GET' | 'POST', body?: unknown) {
  const token = await getAuthToken();

  if (!token) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  });

  const data = await response.json().catch(() => ({ message: 'Invalid response from server' }));
  return NextResponse.json(data, { status: response.status });
}
