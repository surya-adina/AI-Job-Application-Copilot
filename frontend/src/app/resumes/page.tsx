import Link from 'next/link';
import { redirect } from 'next/navigation';
import { getAuthToken } from '@/lib/auth/server';
import { LogoutButton } from '@/components/auth/logout-button';
import { DeleteResumeButton } from './delete-resume-button';

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

export default async function ResumesPage() {
  const token = await getAuthToken();

  if (!token) {
    redirect('/login');
  }

  const resumes = await getResumes(token);

  return (
    <main className="min-h-screen bg-background px-6 py-8 text-foreground">
      <div className="mx-auto max-w-5xl space-y-8">
        <div className="flex items-center justify-between">
          <Link
            href="/applications"
            className="text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            ← Back to Applications
          </Link>
          <LogoutButton />
        </div>

        <section className="rounded-3xl border bg-card p-8 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Resume Library
              </p>
              <h1 className="mt-2 text-3xl font-bold">Saved resumes</h1>
              <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
                Save your resumes once and reuse them across multiple job
                applications.
              </p>
            </div>
            <Link
              href="/applications/new"
              className="rounded-xl border px-5 py-3 text-sm font-semibold transition hover:bg-muted"
            >
              New Application
            </Link>
            <Link
              href="/resumes/new"
              className="rounded-xl bg-foreground px-5 py-3 text-sm font-semibold text-background transition hover:opacity-90"
            >
              Add Resume
            </Link>
            
          </div>
        </section>

        {resumes.length === 0 ? (
          <section className="rounded-3xl border bg-card p-8 text-center shadow-sm">
            <h2 className="text-xl font-semibold">No resumes yet</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Add your first resume so you can use it when creating job
              applications.
            </p>
            <Link
              href="/resumes/new"
              className="mt-6 inline-flex rounded-xl bg-foreground px-5 py-3 text-sm font-semibold text-background transition hover:opacity-90"
            >
              Add your first resume
            </Link>
          </section>
        ) : (
          <section className="grid gap-4">
            {resumes.map((resume) => {
              const createdDate = new Intl.DateTimeFormat('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              }).format(new Date(resume.createdAt));

              return (
                <article
                  key={resume.id}
                  className="rounded-2xl border bg-card p-6 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-semibold">{resume.title}</h2>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Added {createdDate}
                      </p>
                    </div>

                    <DeleteResumeButton resumeId={resume.id} title={resume.title} />
                  </div>

                  <p className="mt-4 line-clamp-3 text-sm text-muted-foreground">
                    {resume.rawText}
                  </p>
                </article>
              );
            })}
          </section>
        )}
      </div>
    </main>
  );
}
