import Link from 'next/link';
import { redirect } from 'next/navigation';
import { getAuthToken } from '@/lib/auth/server';
import { getApplications } from '@/lib/api/applications';
import { LogoutButton } from '@/components/auth/logout-button';
import { DeleteApplicationButton } from './delete-application-button';
import { ThemeToggle } from '@/components/theme/theme-toggle';

function formatStatus(status: string) {
  return status
    .toLowerCase()
    .replace('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default async function ApplicationsPage() {
  const token = await getAuthToken();

  if (!token) {
    redirect('/login');
  }

  const applications = await getApplications(token);

  return (
    <main className="min-h-screen bg-background px-6 py-10 text-foreground">
      <section className="mx-auto max-w-5xl">
        <header className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="text-sm font-medium text-cyan-500">Applications</p>
            <h1 className="mt-2 text-4xl font-bold tracking-tight">Job Applications</h1>
          </div>

          <nav className="flex flex-wrap items-center gap-3" aria-label="Account and actions">
            <ThemeToggle />
            <Link
              href="/resumes"
              className="rounded-xl border px-4 py-2 text-sm font-medium transition hover:bg-muted"
            >
              Saved Resumes
            </Link>
            <Link
              href="/applications/new"
              className="rounded-xl bg-foreground px-4 py-2 text-sm font-semibold text-background transition hover:opacity-90"
            >
              New Application
            </Link>
            <LogoutButton />
          </nav>
        </header>

        {applications.length === 0 ? (
          <div className="mt-10 rounded-2xl border p-8 text-muted-foreground">
            No applications yet. Create one to analyze a resume against a job.
          </div>
        ) : (
          <ul className="mt-10 space-y-4">
            {applications.map((application) => (
              <li
                key={application.id}
                className="relative rounded-2xl border p-6 transition hover:border-cyan-500/60 hover:bg-muted/40"
              >
                <div className="flex items-start justify-between gap-6">
                  <div className="min-w-0">
                    <h2 className="text-lg font-semibold">
                      {/* The link covers the whole card; the delete button sits above it. */}
                      <Link
                        href={`/applications/${application.id}`}
                        className="after:absolute after:inset-0 after:rounded-2xl focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-cyan-500"
                      >
                        {application.job.company}
                      </Link>
                    </h2>
                    <p className="mt-1 text-muted-foreground">{application.job.title}</p>

                    <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                      <span className="rounded-full border px-2.5 py-0.5 text-xs font-medium">
                        {formatStatus(application.status)}
                      </span>
                      <span>Resume: {application.resume.title}</span>
                      <span>Added {formatDate(application.createdAt)}</span>
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-col items-end gap-3">
                    {application.analysis?.score !== undefined ? (
                      <div className="text-right">
                        <p className="text-3xl font-semibold leading-none text-cyan-500">{application.analysis.score}%</p>
                        <p className="mt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Match</p>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">Not analyzed yet</p>
                    )}

                    <div className="relative z-10">
                      <DeleteApplicationButton
                        applicationId={application.id}
                        company={application.job.company}
                        role={application.job.title}
                      />
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
