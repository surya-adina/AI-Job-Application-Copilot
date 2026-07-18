import Link from 'next/link';
import { getWorkspace } from '@/lib/api/workspace';
import { redirect } from 'next/navigation';
import { getAuthToken } from '@/lib/auth/server';


const actions = [
  {
    title: 'View Resume Analysis',
    description: 'Review match score, required skills, preferred skills, and gaps.',
    href: 'analysis',
    available: true,
  },
  {
    title: 'Review Resume Suggestions',
    description: 'See prioritized, evidence-backed resume improvement guidance.',
    href: 'review',
    available: true,
  },
  {
    title: 'View / Generate Cover Letter',
    description: 'Create or view a tailored cover letter using the resume and job context.',
    href: 'cover-letter',
    available: true,
  },
  {
    title: 'Prepare for Interview',
    description: 'Generate technical, behavioral, and project-specific questions for this role.',
    href: 'interview-prep',
    available: true,
  },
];

const activity = [
  'Resume analysis completed',
  'Resume review generated',
  'Application workspace created',
];

export default async function ApplicationPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;
  const token = await getAuthToken();

  if (!token) {
    redirect('/login');
  }

  const workspace = await getWorkspace(applicationId, token);
  const progress = [
  { label: 'Resume Uploaded', done: workspace.progress.resumeUploaded },
  { label: 'Analysis Complete', done: workspace.progress.analysisComplete },
  { label: 'Resume Review Complete', done: workspace.progress.resumeReviewComplete },
  { label: 'Cover Letter', done: workspace.progress.coverLetterComplete },
  { label: 'Interview Prep', done: workspace.progress.interviewPrepComplete },
];
  return (
    <main className="min-h-screen bg-background px-6 py-10 text-foreground md:px-10">
      <section className="mx-auto max-w-6xl space-y-8">
        <Link href="/applications" className="text-sm font-medium text-cyan-500 hover:underline">
          ← Back to Applications
        </Link>

        <header className="flex flex-col gap-6 rounded-2xl border p-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{workspace.application.company}</p>
            <h1 className="mt-2 text-4xl font-bold">{workspace.application.role}</h1>
            <p className="mt-3 text-muted-foreground">Status: {workspace.application.status}</p>
          </div>

          <div className="text-left md:text-right">
            <p className="text-sm text-muted-foreground">Resume Match</p>
            <p className="text-5xl font-bold text-cyan-500">{workspace.analysis?.score ?? null}%</p>
            <p className="mt-2 text-sm text-muted-foreground">Strong required-skill match</p>
          </div>
        </header>

        <section className="rounded-2xl border p-6">
          <h2 className="text-xl font-semibold">Progress</h2>

          <div className="mt-5 grid gap-3 md:grid-cols-5">
            {progress.map((item) => (
              <div
                key={item.label}
                className={
                  item.done
                    ? 'rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-500'
                    : 'rounded-xl border p-4 text-muted-foreground'
                }
              >
                <p className="text-sm font-medium">
                  {item.done ? '✓' : '○'} {item.label}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold">Quick Actions</h2>

          <div className="mt-5 grid gap-5 md:grid-cols-2">
            {actions.map((action) => {
              const href = action.available
                ? `/applications/${applicationId}/${action.href}`
                : '#';

              return (
                <Link
                  key={action.title}
                  href={href}
                  className={
                    action.available
                      ? 'rounded-2xl border p-6 transition hover:border-cyan-500'
                      : 'cursor-not-allowed rounded-2xl border p-6 opacity-50'
                  }
                >
                  <h3 className="text-lg font-semibold">{action.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">
                    {action.description}
                  </p>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="rounded-2xl border p-6">
          <h2 className="text-xl font-semibold">Recent Activity</h2>

          <div className="mt-5 space-y-3">
            {activity.map((item) => (
              <div key={item} className="rounded-xl bg-cyan-500/5 px-4 py-3 text-sm text-muted-foreground">
                {item}
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}