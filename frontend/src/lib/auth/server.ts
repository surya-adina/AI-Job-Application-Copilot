import { cookies } from 'next/headers';

export async function getAuthToken() {
  const cookieStore = await cookies();
  return cookieStore.get('accessToken')?.value ?? null;
}