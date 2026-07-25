import { NextResponse } from 'next/server';
import { getAuthToken } from '@/lib/auth/server';

const API_BASE = process.env.BACKEND_API_URL ?? 'http://localhost:4000';

type RouteParams = {
  params: Promise<{
    resumeId: string;
  }>;
};

export async function DELETE(_request: Request, { params }: RouteParams) {
  const token = await getAuthToken();

  if (!token) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  const { resumeId } = await params;

  const response = await fetch(`${API_BASE}/resumes/${resumeId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}
