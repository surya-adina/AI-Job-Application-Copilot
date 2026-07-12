'use client';
import Link from 'next/link';
import { useState, useEffect } from 'react';
import { createResumeReviewForApplication, getResumeReviewForApplication } from '@/lib/api/resume-review';
import type { ResumeReviewReport } from '@/types/resume-review';

export default function ResumeReviewClient({
  applicationId,
}: {
  applicationId: string;
}) {
  const [review, setReview] = useState<ResumeReviewReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = process.env.NEXT_PUBLIC_DEV_TOKEN;

    if (!token) {
      setError('NEXT_PUBLIC_DEV_TOKEN is not configured');
      return;
    }
    const devToken = token;
    async function loadSavedReview() {
      try {
        const savedReview = await getResumeReviewForApplication(
          applicationId,
          devToken,
        );

        setReview(savedReview);
      } catch {
        // No saved review yet. User can generate one.
      }
    }

    loadSavedReview();
  }, [applicationId]);
  async function handleGenerateReview() {
    const token = process.env.NEXT_PUBLIC_DEV_TOKEN;

    if (!token) {
      setError('NEXT_PUBLIC_DEV_TOKEN is not configured');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const result = await createResumeReviewForApplication(
        applicationId,
        token,
      );

      setReview(result);
    } catch {
      setError('Failed to generate resume review.');
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
          <p className="text-sm font-medium text-cyan-400">Resume Review</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">
            Prioritized Resume Guidance
          </h1>
          <p className="mt-3 max-w-2xl text-slate-400">
            Suggestions are grounded in the job description, analysis results,
            and resume evidence.
          </p>
        </header>

        <button
          onClick={handleGenerateReview}
          disabled={loading}
          className="rounded-xl bg-cyan-500 px-5 py-3 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? 'Generating Review...' : 'Generate Resume Review'}
        </button>

        {error && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">
            {error}
          </p>
        )}

        {review && (
          <>
            <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="text-xl font-semibold">Summary</h2>
              <p className="mt-3 leading-7 text-slate-400">
                {review.review.summary}
              </p>
            </section>

            <section className="space-y-5">
              {review.review.suggestions.map((item) => (
                <article
                  key={item.title}
                  className="rounded-2xl border border-slate-800 bg-slate-900 p-6"
                >
                  <div className="flex items-center gap-3">
                    <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-300">
                      {item.priority ?? 'MEDIUM'}
                    </span>
                    <span className="text-sm text-slate-400">
                      {item.target_section ?? 'Resume'}
                    </span>
                  </div>

                  <h2 className="mt-3 text-xl font-semibold">{item.title}</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    {item.why}
                  </p>

                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl bg-slate-950 p-4">
                      <p className="text-sm font-medium text-slate-300">
                        Evidence
                      </p>
                      <ul className="mt-3 space-y-2 text-sm text-slate-400">
                        {item.evidence.map((point) => (
                          <li key={point}>• {point}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="rounded-xl bg-slate-950 p-4">
                      <p className="text-sm font-medium text-slate-300">
                        Action
                      </p>
                      <p className="mt-3 text-sm leading-6 text-slate-400">
                        {item.action}
                      </p>
                    </div>
                  </div>
                </article>
              ))}
            </section>
          </>
        )}
      </section>
    </main>
  );
}