import { NextResponse } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000';

export async function POST(request: Request) {
  const body = await request.json();

  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    return NextResponse.json(
      { message: 'Invalid email or password' },
      { status: response.status },
    );
  }

  const data = await response.json();

  const nextResponse = NextResponse.json({ success: true });

  nextResponse.cookies.set('accessToken', data.accessToken, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
  });

  return nextResponse;
}