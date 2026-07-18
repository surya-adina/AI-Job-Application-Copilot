import { NextResponse } from 'next/server';
import { getAuthToken } from '@/lib/auth/server';

const API_BASE =
  process.env.BACKEND_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  'http://localhost:4000';

export async function proxyToBackend(path: string, method: 'GET' | 'POST') {
  const token = await getAuthToken();

  if (!token) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  return NextResponse.json(data, { status: response.status });
}