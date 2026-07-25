import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';
import { getAuthToken } from '@/lib/auth/server';
import { DeleteResumeButton } from '../delete-resume-button';

const API_BASE = process.env.BACKEND_API_URL ?? 'http://localhost:4000';

type Resume = {
  id: string;
  title: string;
  rawText: string;
  createdAt: string;
};

async function getResume(resumeId: string, token: string): Promise<Resume> {
  const response = await fetch(`${API_BASE}/resumes/${resumeId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  });

  if (response.status === 404) {
    notFound();
  }

  if (!response.ok) {
    throw new Error('Failed to load resume');
  }

  return response.json();
}

export default async function ResumeDetailsPage({
  params,
}: {
  params: Promise<{ resumeId: string }>;
}) {
  const token = await getAuthToken();

  if (!token) {
    redirect('/login');
  }

  const { resumeId } = await params;
  const resume = await getResume(resumeId, token);

  const createdDate = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(resume.createdAt));

  return (
    <main className="min-h-screen bg-background px-6 py-8 text-foreground">
      <div className="mx-auto max-w-5xl space-y-8">
        <Link
          href="/resumes"
          className="text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          ← Back to Resumes
        </Link>

        <section className="rounded-3xl border bg-card p-8 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Saved Resume
              </p>
              <h1 className="mt-2 text-3xl font-bold">{resume.title}</h1>
              <p className="mt-3 text-sm text-muted-foreground">
                Added {createdDate}
              </p>
            </div>

            <DeleteResumeButton resumeId={resume.id} title={resume.title} />
          </div>
        </section>

        <section className="rounded-3xl border bg-card p-8 shadow-sm">
          <h2 className="text-xl font-semibold">Extracted resume text</h2>
          <pre className="mt-6 whitespace-pre-wrap rounded-2xl border bg-background p-5 text-sm leading-7 text-muted-foreground">
            {resume.rawText}
          </pre>
        </section>
      </div>
    </main>
  );
}
