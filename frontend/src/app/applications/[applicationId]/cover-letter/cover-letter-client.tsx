'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  createCoverLetterForApplication,
  getCoverLetterForApplication,
} from '@/lib/api/cover-letter';
import type { CoverLetterReport } from '@/types/cover-letter';

export default function CoverLetterClient({
  applicationId,
}: {
  applicationId: string;
}) {
  const [coverLetter, setCoverLetter] = useState<CoverLetterReport | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {

    async function loadSavedCoverLetter() {
      try {
        const savedCoverLetter = await getCoverLetterForApplication(
          applicationId,
        );

        setCoverLetter(savedCoverLetter);
      } catch {
        // No saved cover letter yet.
      }
    }

    loadSavedCoverLetter();
  }, [applicationId]);

  async function handleGenerateCoverLetter() {
    try {
      setLoading(true);
      setError('');

      const result = await createCoverLetterForApplication(
        applicationId,
      );

      setCoverLetter(result);
    } catch {
      setError('Failed to generate cover letter.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100 md:px-10">
      <section className="mx-auto max-w-5xl space-y-8">
        <Link
          href={`/applications/${applicationId}`}
          className="inline-flex text-sm font-medium text-cyan-500 hover:underline"
        >
          ← Back to Application
        </Link>

        <header>
          <p className="text-sm font-medium text-cyan-400">Cover Letter</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">
            Job-Specific Cover Letter
          </h1>
          <p className="mt-3 max-w-2xl text-slate-400">
            Generate a truthful cover letter based on your resume and the
            selected job description.
          </p>
        </header>

        <button
          onClick={handleGenerateCoverLetter}
          disabled={loading}
          className="rounded-xl bg-cyan-500 px-5 py-3 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? 'Generating Cover Letter...' : 'Generate Cover Letter'}
        </button>

        {error && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">
            {error}
          </p>
        )}

        {coverLetter && (
          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <h2 className="text-xl font-semibold">Generated Cover Letter</h2>
              <p className="text-sm text-slate-500">
                Last updated{' '}
                {new Date(coverLetter.updatedAt).toLocaleString()}
              </p>
            </div>

            <div className="whitespace-pre-wrap rounded-xl bg-slate-950 p-5 leading-7 text-slate-300">
              {coverLetter.content}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}