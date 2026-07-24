'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';

type Resume = {
  id: string;
  title: string;
  rawText: string;
  createdAt: string;
};

type NewApplicationFormProps = {
  resumes: Resume[];
};

export function NewApplicationForm({ resumes }: NewApplicationFormProps) {
  const router = useRouter();

  const [resumeId, setResumeId] = useState(resumes[0]?.id ?? '');
  const [company, setCompany] = useState('');
  const [title, setTitle] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [jdText, setJdText] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');

  async function createJob() {
    const response = await fetch('/api/jobs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        company: company.trim() || undefined,
        title: title.trim(),
        jdText: jdText.trim(),
        sourceUrl: sourceUrl.trim() || undefined,
      }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.message ?? 'Failed to create job');
    }

    return response.json();
  }

  async function createApplication(jobId: string) {
    const response = await fetch('/api/applications', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        jobId,
        resumeId,
        notes: notes.trim() || undefined,
      }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.message ?? 'Failed to create application');
    }

    return response.json();
  }

  async function runAnalysis(applicationId: string) {
    const response = await fetch(`/api/applications/${applicationId}/analysis`, {
      method: 'POST',
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.message ?? 'Application created, but analysis failed');
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setStatusMessage('');
    setIsSubmitting(true);

    try {
      if (!resumeId) {
        throw new Error('Select a saved resume first');
      }

      setStatusMessage('Creating job...');
      const job = await createJob();

      setStatusMessage('Creating application...');
      const application = await createApplication(job.id);

      setStatusMessage('Running AI analysis...');
      await runAnalysis(application.id);

      router.push(`/applications/${application.id}`);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to create application',
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (resumes.length === 0) {
    return (
      <div className="rounded-2xl border bg-background p-6">
        <h2 className="text-xl font-semibold">Add a resume first</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          You need at least one saved resume before creating an application.
        </p>
        <Link
          href="/resumes/new"
          className="mt-5 inline-flex rounded-xl bg-foreground px-5 py-3 text-sm font-semibold text-background transition hover:opacity-90"
        >
          Add Resume
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label htmlFor="resumeId" className="text-sm font-medium">
          Saved resume
        </label>
        <select
          id="resumeId"
          required
          value={resumeId}
          onChange={(event) => setResumeId(event.target.value)}
          className="mt-2 w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
        >
          {resumes.map((resume) => (
            <option key={resume.id} value={resume.id}>
              {resume.title}
            </option>
          ))}
        </select>
        <p className="mt-2 text-xs text-muted-foreground">
          This resume will be reused for this application.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <label htmlFor="company" className="text-sm font-medium">
            Company
          </label>
          <input
            id="company"
            type="text"
            value={company}
            onChange={(event) => setCompany(event.target.value)}
            className="mt-2 w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
            placeholder="Waymark"
          />
        </div>

        <div>
          <label htmlFor="title" className="text-sm font-medium">
            Role / job title
          </label>
          <input
            id="title"
            type="text"
            required
            minLength={2}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="mt-2 w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
            placeholder="Software Engineer"
          />
        </div>
      </div>

      <div>
        <label htmlFor="sourceUrl" className="text-sm font-medium">
          Job posting URL optional
        </label>
        <input
          id="sourceUrl"
          type="url"
          value={sourceUrl}
          onChange={(event) => setSourceUrl(event.target.value)}
          className="mt-2 w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
          placeholder="https://company.com/jobs/software-engineer"
        />
      </div>

      <div>
        <label htmlFor="jdText" className="text-sm font-medium">
          Job description
        </label>
        <textarea
          id="jdText"
          required
          minLength={50}
          value={jdText}
          onChange={(event) => setJdText(event.target.value)}
          className="mt-2 min-h-[320px] w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
          placeholder="Paste the full job description here..."
        />
      </div>

      <div>
        <label htmlFor="notes" className="text-sm font-medium">
          Notes optional
        </label>
        <textarea
          id="notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          className="mt-2 min-h-[120px] w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
          placeholder="Anything you want to remember about this application..."
        />
      </div>

      {statusMessage ? (
        <p className="rounded-xl border bg-background px-4 py-3 text-sm text-muted-foreground">
          {statusMessage}
        </p>
      ) : null}

      {error ? (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-xl bg-foreground px-5 py-3 text-sm font-semibold text-background transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? 'Creating application...' : 'Create Application'}
      </button>
    </form>
  );
}
