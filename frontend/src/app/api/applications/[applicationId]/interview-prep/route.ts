import { NextResponse } from 'next/server';
import { getAuthToken } from '@/lib/auth/server';

const API_BASE = process.env.BACKEND_API_URL ?? 'http://localhost:4000';

type RouteContext = {
  params: Promise<{
    applicationId: string;
  }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const token = await getAuthToken();

  if (!token) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  const { applicationId } = await context.params;

  const response = await fetch(
    `${API_BASE}/applications/${applicationId}/interview-prep`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: 'no-store',
    },
  );

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}

export async function POST(_request: Request, context: RouteContext) {
  const token = await getAuthToken();

  if (!token) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  const { applicationId } = await context.params;

  const response = await fetch(
    `${API_BASE}/applications/${applicationId}/interview-prep`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: 'no-store',
    },
  );

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}