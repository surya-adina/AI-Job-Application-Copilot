'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { decideAgentRun, getAgentRun, listAgentRuns, startAgentRun } from '@/lib/api/agent-runs';
import type { AgentDecision, AgentRun, AgentStep } from '@/types/agent-run';

const NODE_LABELS: Record<string, string> = {
  plan: 'Plan',
  gather_evidence: 'Search resume evidence',
  draft: 'Draft paragraphs',
  verify: 'Fact-check claims',
  revise: 'Revise rejected paragraphs',
  human_review: 'Your decision',
};

const STATUS_STYLES: Record<AgentRun['status'], string> = {
  RUNNING: 'border-cyan-500/40 text-cyan-300',
  AWAITING_REVIEW: 'border-amber-500/40 text-amber-300',
  COMPLETED: 'border-emerald-500/40 text-emerald-300',
  REJECTED: 'border-slate-500/40 text-slate-300',
  FAILED: 'border-red-500/40 text-red-300',
};

function stepSummary(step: AgentStep): string | null {
  if (step.node !== 'verify' || !step.detail) {
    return null;
  }
  const sections = Object.values(step.detail) as { passed: boolean; problems: string[] }[];
  const failing = sections.filter((section) => !section.passed).length;
  return failing === 0 ? 'All paragraphs passed' : `${failing} paragraph(s) had unsupported claims`;
}

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
        const runs = await listAgentRuns(applicationId);
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
      setRun(await startAgentRun(applicationId, instructions.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start the agent.');
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
      setError(err instanceof Error ? err.message : 'Failed to submit your decision.');
    } finally {
      setBusy(null);
    }
  }

  const review = run?.status === 'AWAITING_REVIEW' ? run.review : null;
  const canStart = !busy && run?.status !== 'AWAITING_REVIEW';

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
          <p className="text-sm font-medium text-cyan-400">Cover Letter Agent</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Draft, fact-check, then you decide</h1>
          <p className="mt-3 max-w-2xl text-slate-400">
            The agent plans the letter, pulls supporting lines from your resume, drafts each paragraph, and
            rejects any claim your resume does not back up before showing you the result. Nothing is saved
            until you approve or edit it.
          </p>
        </header>

        <section className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <label htmlFor="instructions" className="text-sm font-medium text-slate-300">
            Instructions (optional)
          </label>
          <textarea
            id="instructions"
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            maxLength={1000}
            rows={2}
            placeholder="For example: emphasize API performance work and keep it under 250 words."
            className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-slate-200"
          />
          <button
            onClick={handleStart}
            disabled={!canStart}
            className="rounded-xl bg-cyan-500 px-5 py-3 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy === 'start' ? 'Agent is working… (about 10–20 seconds)' : 'Run agent'}
          </button>
          {run?.status === 'AWAITING_REVIEW' && (
            <p className="text-sm text-slate-500">Decide on the current draft before starting a new run.</p>
          )}
        </section>

        {error && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</p>
        )}

        {run && (
          <section className="space-y-6 rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <div className="flex flex-wrap items-center gap-3">
              <span className={`rounded-full border px-3 py-1 text-sm ${STATUS_STYLES[run.status]}`}>
                {run.status.replace('_', ' ').toLowerCase()}
              </span>
              <span className="text-sm text-slate-500">
                {run.totals.llmCalls} LLM calls · ${run.totals.costUsd.toFixed(4)} ·{' '}
                {(run.totals.latencyMs / 1000).toFixed(1)}s of agent time
              </span>
            </div>

            <ol className="space-y-2">
              {run.steps.map((step) => (
                <li key={step.id} className="flex flex-wrap items-baseline gap-x-3 text-sm">
                  <span className="w-6 text-slate-600">{step.index + 1}.</span>
                  <span className={step.status === 'failed' ? 'text-red-300' : 'text-slate-200'}>
                    {NODE_LABELS[step.node] ?? step.node}
                  </span>
                  <span className="text-slate-500">
                    {step.latencyMs} ms{step.aiRuns.length > 0 ? ` · ${step.aiRuns.length} LLM call(s)` : ''}
                  </span>
                  {stepSummary(step) && <span className="text-slate-400">· {stepSummary(step)}</span>}
                  {step.error && <span className="text-red-300">· {step.error.message}</span>}
                </li>
              ))}
            </ol>

            {review && (
              <div className="space-y-5">
                {Object.keys(review.unresolved).length > 0 && (
                  <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
                    Some claims could not be verified against your resume after {Object.values(review.revisions).reduce((a, b) => Math.max(a, b), 0)} revision(s).
                    They are marked below. Edit or reject the draft if they are not accurate.
                  </p>
                )}

                {review.paragraphs.map((paragraph) => (
                  <article key={paragraph.key} className="space-y-3 rounded-xl bg-slate-950 p-5">
                    <p className="leading-7 text-slate-200">{paragraph.text}</p>
                    {paragraph.claims.length > 0 && (
                      <ul className="space-y-1 text-sm">
                        {paragraph.claims.map((claim, index) => (
                          <li key={index} className={claim.supported ? 'text-emerald-300' : 'text-amber-300'}>
                            {claim.supported ? '✓' : '✗'} {claim.text}
                            {!claim.supported && (
                              <span className="text-slate-500"> ({claim.reasons.join('; ')})</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                    {review.unresolved[paragraph.key] && (
                      <ul className="space-y-1 text-sm text-amber-300">
                        {review.unresolved[paragraph.key].map((problem, index) => (
                          <li key={index}>⚠ {problem}</li>
                        ))}
                      </ul>
                    )}
                  </article>
                ))}

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
                        Save my edit
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
                      Reject
                    </button>
                  </div>
                )}
              </div>
            )}

            {run.status === 'COMPLETED' && run.finalText && (
              <div className="space-y-3">
                <p className="text-sm text-emerald-300">
                  {run.decision?.edited ? 'Your edited letter' : 'The approved letter'} was saved as this
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
              <p className="text-sm text-slate-400">You rejected this draft. Nothing was saved. Run the agent again to get a new one.</p>
            )}

            {run.status === 'FAILED' && (
              <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
                The agent failed{run.error?.message ? `: ${run.error.message}` : ''}. Every LLM call it made is still
                logged. Try running it again.
              </p>
            )}
          </section>
        )}
      </section>
    </main>
  );
}
