import Link from 'next/link';
import { redirect } from 'next/navigation';
import { getAuthToken } from '@/lib/auth/server';
import { getApplications } from '@/lib/api/applications';
import { LogoutButton } from '@/components/auth/logout-button';

export default async function ApplicationsPage() {
  const token = await getAuthToken();

  if (!token) {
    redirect('/login');
  }

  const applications = await getApplications(token);

  return (
    <main className="min-h-screen bg-background px-6 py-10 text-foreground">
      <section className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-cyan-500">Applications</p>

            <h1 className="mt-2 text-4xl font-bold">Job Applications</h1>
          </div>
          <Link
            href="/applications/new"
            className="rounded-xl bg-foreground px-5 py-3 text-sm font-semibold text-background transition hover:opacity-90"
          >
            New Application
          </Link>

          <Link
            href="/resumes"
            className="rounded-xl border px-5 py-3 text-sm font-semibold transition hover:bg-muted"
          >
            Saved Resumes
          </Link>
          <LogoutButton />
        </div>

        {applications.length === 0 ? (
          <div className="mt-10 rounded-2xl border p-8 text-muted-foreground">
            No applications found yet.
          </div>
        ) : (
          <div className="mt-10 space-y-5">
            {applications.map((application) => (
              <Link
                key={application.id}
                href={`/applications/${application.id}`}
                className="block rounded-2xl border p-6 transition hover:border-cyan-500"
              >
                <div className="flex items-center justify-between gap-6">
                  <div>
                    <h2 className="text-xl font-semibold">
                      {application.job.company}
                    </h2>

                    <p className="mt-2 text-muted-foreground">
                      {application.job.title}
                    </p>

                    <p className="mt-3 text-sm text-muted-foreground">
                      Resume: {application.resume.title}
                    </p>
                  </div>

                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">
                      {application.status}
                    </p>

                    {application.analysis?.score !== undefined && (
                      <p className="mt-2 text-3xl font-bold text-cyan-500">
                        {application.analysis.score}%
                      </p>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}