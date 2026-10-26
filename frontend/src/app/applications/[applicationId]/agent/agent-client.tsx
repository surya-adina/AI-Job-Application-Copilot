'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { explainProblems } from '@/lib/agent-feedback';
import { decideAgentRun, getAgentRun, listAgentRuns, startAgentRun } from '@/lib/api/agent-runs';
import type { AgentDecision, AgentRun, CoverLetterReview } from '@/types/agent-run';

const STATUS_LABELS: Record<AgentRun['status'], { label: string; style: string }> = {
  RUNNING: { label: 'Writing your letter', style: 'border-cyan-500/40 text-cyan-300' },
  AWAITING_REVIEW: { label: 'Ready for your review', style: 'border-amber-500/40 text-amber-300' },
  COMPLETED: { label: 'Saved', style: 'border-emerald-500/40 text-emerald-300' },
  REJECTED: { label: 'Discarded', style: 'border-slate-500/40 text-slate-300' },
  FAILED: { label: 'Something went wrong', style: 'border-red-500/40 text-red-300' },
};

export default function AgentClient({ applicationId }: { applicationId: string }) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [instructions, setInstructions] = useState('');
  const [editing, setEditing] = useState(false);
  const [editedText, setEditedText] = useState('');
  const [busy, setBusy] = useState<'start' | 'decide' | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadLatestRun() {
      try {
        const runs = await listAgentRuns(applicationId, 'cover_letter');
        if (runs.length > 0) {
          setRun(await getAgentRun(applicationId, runs[0].id));
        }
      } catch {
        // No runs yet.
      }
    }

    loadLatestRun();
  }, [applicationId]);

  async function handleStart() {
    try {
      setBusy('start');
      setError('');
      setEditing(false);
      setRun(await startAgentRun(applicationId, 'cover_letter', instructions.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't start the cover letter. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function handleDecision(decision: AgentDecision) {
    if (!run) {
      return;
    }
    try {
      setBusy('decide');
      setError('');
      setRun(await decideAgentRun(applicationId, run.id, decision));
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't save your decision. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  const review = run?.status === 'AWAITING_REVIEW' ? (run.review as CoverLetterReview | null) : null;
  const needsCheck = review ? Object.keys(review.unresolved).length > 0 : false;
  const canStart = !busy && run?.status !== 'AWAITING_REVIEW';
  const status = run ? STATUS_LABELS[run.status] : null;

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
          <p className="text-sm font-medium text-cyan-400">Cover Letter Assistant</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Draft a cover letter from your resume</h1>
          <p className="mt-3 max-w-2xl text-slate-400">
            Each paragraph is written from lines in your resume, and every skill and figure it mentions is checked
            against them. The check does not judge tone or how strongly experience is described, so read the draft
            before approving it. Nothing is saved until you approve or edit it.
          </p>
        </header>

        <section className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <label htmlFor="instructions" className="text-sm font-medium text-slate-300">
            Anything to emphasize? (optional)
          </label>
          <textarea
            id="instructions"
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            maxLength={1000}
            rows={2}
            placeholder="For example: highlight my API performance work and keep it under 250 words."
            className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-slate-200"
          />
          <button
            onClick={handleStart}
            disabled={!canStart}
            className="rounded-xl bg-cyan-500 px-5 py-3 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy === 'start' ? 'Writing your letter… this takes about 15 seconds' : 'Write my cover letter'}
          </button>
          {run?.status === 'AWAITING_REVIEW' && (
            <p className="text-sm text-slate-500">Approve, edit or discard the current draft before writing a new one.</p>
          )}
        </section>

        {error && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</p>
        )}

        {run && status && (
          <section className="space-y-6 rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <span className={`inline-block rounded-full border px-3 py-1 text-sm ${status.style}`}>{status.label}</span>

            {review && (
              <div className="space-y-5">
                {needsCheck ? (
                  <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
                    A few statements couldn&apos;t be matched to your resume. They&apos;re listed under each paragraph.
                    Edit them if they aren&apos;t accurate before approving.
                  </p>
                ) : (
                  <p className="rounded-xl border border-slate-700 bg-slate-950 p-4 text-sm text-slate-300">
                    No skills or figures were found that your resume doesn&apos;t state. Review the wording before
                    approving.
                  </p>
                )}

                {review.paragraphs.map((paragraph) => {
                  const notes = explainProblems(review.unresolved[paragraph.key] ?? []);
                  return (
                    <article key={paragraph.key} className="space-y-3 rounded-xl bg-slate-950 p-5">
                      <p className="leading-7 text-slate-200">{paragraph.text}</p>
                      {notes.length > 0 && (
                        <div className="space-y-1 text-sm text-amber-300">
                          <p className="font-medium">Please check:</p>
                          <ul className="list-disc space-y-1 pl-5">
                            {notes.map((note) => (
                              <li key={note}>{note}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </article>
                  );
                })}

                {editing ? (
                  <div className="space-y-3">
                    <textarea
                      value={editedText}
                      onChange={(event) => setEditedText(event.target.value)}
                      rows={16}
                      maxLength={10000}
                      className="w-full rounded-xl border border-slate-700 bg-slate-950 p-4 leading-7 text-slate-200"
                    />
                    <div className="flex flex-wrap gap-3">
                      <button
                        onClick={() => handleDecision({ action: 'edit', text: editedText })}
                        disabled={!!busy || !editedText.trim()}
                        className="rounded-xl bg-cyan-500 px-5 py-2 font-medium text-slate-950 disabled:opacity-60"
                      >
                        Save my version
                      </button>
                      <button
                        onClick={() => setEditing(false)}
                        disabled={!!busy}
                        className="rounded-xl border border-slate-700 px-5 py-2 text-slate-300"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-3">
                    <button
                      onClick={() => handleDecision({ action: 'approve' })}
                      disabled={!!busy}
                      className="rounded-xl bg-emerald-500 px-5 py-2 font-medium text-slate-950 disabled:opacity-60"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => {
                        setEditedText(review.letter);
                        setEditing(true);
                      }}
                      disabled={!!busy}
                      className="rounded-xl border border-cyan-500/50 px-5 py-2 text-cyan-300 disabled:opacity-60"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDecision({ action: 'reject' })}
                      disabled={!!busy}
                      className="rounded-xl border border-red-500/40 px-5 py-2 text-red-300 disabled:opacity-60"
                    >
                      Discard
                    </button>
                  </div>
                )}
              </div>
            )}

            {run.status === 'COMPLETED' && run.finalText && (
              <div className="space-y-3">
                <p className="text-sm text-emerald-300">
                  {run.decision?.edited ? 'Your edited letter' : 'Your letter'} was saved as this
                  application&apos;s{' '}
                  <Link href={`/applications/${applicationId}/cover-letter`} className="underline">
                    cover letter
                  </Link>
                  .
                </p>
                <div className="whitespace-pre-wrap rounded-xl bg-slate-950 p-5 leading-7 text-slate-300">
                  {run.finalText}
                </div>
              </div>
            )}

            {run.status === 'REJECTED' && (
              <p className="text-sm text-slate-400">You discarded this draft, so nothing was saved. Write a new one any time.</p>
            )}

            {run.status === 'FAILED' && (
              <p className="text-sm text-red-300">We couldn&apos;t finish this letter. Please try again in a moment.</p>
            )}
          </section>
        )}
      </section>
    </main>
  );
}
