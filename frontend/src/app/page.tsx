const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000';
const HEALTH_URL = `${API_BASE}/health`;

export default async function Home() {
  let status: string;

  try {
    const res = await fetch(HEALTH_URL, { cache: 'no-store' });
    status = res.ok ? 'up' : `error (${res.status})`;
  } catch {
    status = 'down (fetch failed)';
  }

  return (
    <main style={{ padding: 24 }}>
      <h1>AI Job Application Copilot</h1>
      <p>
        Backend status: <b>{status}</b>
      </p>
      <p style={{ opacity: 0.7 }}>Health URL: {HEALTH_URL}</p>
    </main>
  );
}