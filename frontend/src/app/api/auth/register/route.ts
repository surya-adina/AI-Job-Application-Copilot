import { NextResponse } from 'next/server';

const API_BASE = process.env.BACKEND_API_URL ?? 'http://localhost:4000';

export async function POST(request: Request) {
  const body = await request.json();

  const registerResponse = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const registerData = await registerResponse.json();

  if (!registerResponse.ok) {
    return NextResponse.json(registerData, {
      status: registerResponse.status,
    });
  }

  const loginResponse = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const loginData = await loginResponse.json();

  if (!loginResponse.ok) {
    return NextResponse.json(loginData, {
      status: loginResponse.status,
    });
  }

  const response = NextResponse.json({
    user: registerData,
  });

  response.cookies.set('accessToken', loginData.accessToken, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
  });

  return response;
}
