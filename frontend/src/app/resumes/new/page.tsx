import Link from 'next/link';
import { redirect } from 'next/navigation';
import { getAuthToken } from '@/lib/auth/server';
import { NewResumeForm } from './new-resume-form';

export default async function NewResumePage() {
  const token = await getAuthToken();

  if (!token) {
    redirect('/login');
  }

  return (
    <main className="min-h-screen bg-background px-6 py-8 text-foreground">
      <div className="mx-auto max-w-4xl space-y-8">
        <Link
          href="/resumes"
          className="text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          ← Back to Resumes
        </Link>

        <section className="rounded-3xl border bg-card p-8 shadow-sm">
          <p className="text-sm font-medium text-muted-foreground">
            Resume Library
          </p>
          <h1 className="mt-2 text-3xl font-bold">Add a resume</h1>
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
            Paste your resume text here. You can reuse this saved resume when
            creating job applications.
          </p>

          <div className="mt-8">
            <NewResumeForm />
          </div>
        </section>
      </div>
    </main>
  );
}
