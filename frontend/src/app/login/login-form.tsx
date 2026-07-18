'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginForm() {
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading(true);
      setError('');

      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        setError('Invalid email or password');
        return;
      }

      router.push('/applications');
      router.refresh();
    } catch {
      setError('Something went wrong while logging in.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
      <section className="w-full max-w-md rounded-2xl border p-8 shadow-sm">
        <p className="text-sm font-medium text-cyan-500">
          AI Job Application Copilot
        </p>

        <h1 className="mt-3 text-3xl font-bold">Sign in</h1>

        <p className="mt-2 text-sm text-muted-foreground">
          Use your account to continue working on applications.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <div>
            <label className="text-sm font-medium">Email</label>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-2 w-full rounded-xl border bg-background px-4 py-3 outline-none focus:border-cyan-500"
              type="email"
              required
            />
          </div>

          <div>
            <label className="text-sm font-medium">Password</label>
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-xl border bg-background px-4 py-3 outline-none focus:border-cyan-500"
              type="password"
              required
            />
          </div>

          {error && (
            <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
              {error}
            </p>
          )}

          <button
            disabled={loading}
            className="w-full rounded-xl bg-cyan-500 px-4 py-3 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}