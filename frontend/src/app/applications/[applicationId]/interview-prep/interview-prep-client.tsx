'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  createInterviewPrepForApplication,
  getInterviewPrepForApplication,
} from '@/lib/api/interview-prep';
import type {
  InterviewPrepReport,
  InterviewQuestion,
} from '@/types/interview-prep';

function QuestionSection({
  title,
  questions,
}: {
  title: string;
  questions: InterviewQuestion[];
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-xl font-semibold">{title}</h2>

      <div className="mt-5 space-y-4">
        {questions.map((item, index) => (
          <article
            key={`${item.question}-${index}`}
            className="rounded-xl bg-slate-950 p-5"
          >
            <p className="font-medium text-slate-100">{item.question}</p>

            <p className="mt-3 text-sm leading-6 text-slate-400">
              <span className="font-medium text-slate-300">Why it matters:</span>{' '}
              {item.why_it_matters}
            </p>

            <p className="mt-2 text-sm leading-6 text-slate-400">
              <span className="font-medium text-slate-300">Focus on:</span>{' '}
              {item.suggested_focus}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function InterviewPrepClient({
  applicationId,
}: {
  applicationId: string;
}) {
  const [prep, setPrep] = useState<InterviewPrepReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = process.env.NEXT_PUBLIC_DEV_TOKEN;

    if (!token) {
      setError('NEXT_PUBLIC_DEV_TOKEN is not configured');
      return;
    }

    const devToken = token;

    async function loadSavedPrep() {
      try {
        const savedPrep = await getInterviewPrepForApplication(
          applicationId,
          devToken,
        );

        setPrep(savedPrep);
      } catch {
        // No saved interview prep yet.
      }
    }

    loadSavedPrep();
  }, [applicationId]);

  async function handleGeneratePrep() {
    const token = process.env.NEXT_PUBLIC_DEV_TOKEN;

    if (!token) {
      setError('NEXT_PUBLIC_DEV_TOKEN is not configured');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const result = await createInterviewPrepForApplication(
        applicationId,
        token,
      );

      setPrep(result);
    } catch {
      setError('Failed to generate interview prep.');
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
          <p className="text-sm font-medium text-cyan-400">Interview Prep</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">
            Role-Specific Interview Questions
          </h1>
          <p className="mt-3 max-w-2xl text-slate-400">
            Generate technical, behavioral, and project-specific questions based
            on your resume and the selected job.
          </p>
        </header>

        <button
          onClick={handleGeneratePrep}
          disabled={loading}
          className="rounded-xl bg-cyan-500 px-5 py-3 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? 'Generating Interview Prep...' : 'Generate Interview Prep'}
        </button>

        {error && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">
            {error}
          </p>
        )}

        {prep && (
          <section className="space-y-6">
            <QuestionSection
              title="Technical Questions"
              questions={prep.technical_questions}
            />

            <QuestionSection
              title="Behavioral Questions"
              questions={prep.behavioral_questions}
            />

            <QuestionSection
              title="Project Questions"
              questions={prep.project_questions}
            />

            <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="text-xl font-semibold">Preparation Tips</h2>

              <ul className="mt-4 space-y-2 text-slate-300">
                {prep.preparation_tips.map((tip) => (
                  <li key={tip}>• {tip}</li>
                ))}
              </ul>
            </section>
          </section>
        )}
      </section>
    </main>
  );
}