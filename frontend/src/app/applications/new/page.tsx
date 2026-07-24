import Link from 'next/link';
import { redirect } from 'next/navigation';
import { getAuthToken } from '@/lib/auth/server';
import { NewApplicationForm } from './new-application-form';

const API_BASE = process.env.BACKEND_API_URL ?? 'http://localhost:4000';

type Resume = {
  id: string;
  title: string;
  rawText: string;
  createdAt: string;
};

async function getResumes(token: string): Promise<Resume[]> {
  const response = await fetch(`${API_BASE}/resumes`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error('Failed to load resumes');
  }

  return response.json();
}

export default async function NewApplicationPage() {
  const token = await getAuthToken();

  if (!token) {
    redirect('/login');
  }

  const resumes = await getResumes(token);

  return (
    <main className="min-h-screen bg-background px-6 py-8 text-foreground">
      <div className="mx-auto max-w-5xl space-y-8">
        <Link
          href="/applications"
          className="text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          ← Back to Applications
        </Link>

        <section className="rounded-3xl border bg-card p-8 shadow-sm">
          <p className="text-sm font-medium text-muted-foreground">
            New Application
          </p>
          <h1 className="mt-2 text-3xl font-bold">Create an application</h1>
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
            Select a saved resume, paste a job description, and create a new
            application workspace with AI analysis.
          </p>

          <div className="mt-8">
            <NewApplicationForm resumes={resumes} />
          </div>
        </section>
      </div>
    </main>
  );
}
