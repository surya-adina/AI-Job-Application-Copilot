import { NextResponse } from 'next/server';
import { getAuthToken } from '@/lib/auth/server';

const API_BASE = process.env.BACKEND_API_URL ?? 'http://localhost:4000';

export async function POST(request: Request) {
  const token = await getAuthToken();

  if (!token) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  const body = await request.json();

  const response = await fetch(`${API_BASE}/applications`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}
