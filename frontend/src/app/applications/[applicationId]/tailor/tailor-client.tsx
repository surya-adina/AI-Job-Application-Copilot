'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { explainProblems } from '@/lib/agent-feedback';
import { decideAgentRun, getAgentRun, listAgentRuns, startAgentRun } from '@/lib/api/agent-runs';
import type { AgentDecision, AgentRun, TailorChoice, TailorItem, TailoringReview } from '@/types/agent-run';

type Choice = TailorChoice['choice'];

function defaultChoice(item: TailorItem): Choice {
  // Only clean, actual changes are pre-selected; anything flagged starts as the original.
  return item.passed && !item.unchanged ? 'accept' : 'keep';
}

const CHOICE_LABELS: Record<Choice, string> = {
  accept: 'Use suggestion',
  edit: 'Edit',
  keep: 'Keep original',
};

export default function TailorClient({ applicationId }: { applicationId: string }) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [instructions, setInstructions] = useState('');
  const [choices, setChoices] = useState<Record<number, Choice>>({});
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState<'start' | 'decide' | null>(null);
  const [error, setError] = useState('');
  const [usingNewResume, setUsingNewResume] = useState(false);

  const review = run?.status === 'AWAITING_REVIEW' ? (run.review as TailoringReview | null) : null;

  function showRun(next: AgentRun) {
    setRun(next);
    const items = next.status === 'AWAITING_REVIEW' ? ((next.review as TailoringReview | null)?.items ?? []) : [];
    setChoices(Object.fromEntries(items.map((item) => [item.unitId, defaultChoice(item)])));
    setEdits(Object.fromEntries(items.map((item) => [item.unitId, item.rewritten])));
    setTitle(next.suggestedTitle ?? '');
  }

  useEffect(() => {
    async function loadLatestRun() {
      try {
        const runs = await listAgentRuns(applicationId, 'resume_tailoring');
        if (runs.length > 0) {
          showRun(await getAgentRun(applicationId, runs[0].id));
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
      showRun(await startAgentRun(applicationId, 'resume_tailoring', instructions.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't start tailoring. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function submit(decision: AgentDecision) {
    if (!run) {
      return;
    }
    try {
      setBusy('decide');
      setError('');
      showRun(await decideAgentRun(applicationId, run.id, decision));
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't save your decision. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function switchToNewResume(resumeId: string) {
    try {
      setBusy('decide');
      setError('');
      const response = await fetch(`/api/applications/${applicationId}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resumeId }),
      });
      if (!response.ok) {
        throw new Error();
      }
      setUsingNewResume(true);
    } catch {
      setError("We couldn't switch this application to the new resume. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  function handleSave() {
    if (!review) {
      return;
    }
    const items: TailorChoice[] = review.items.map((item) => {
      const choice = choices[item.unitId] ?? 'keep';
      return choice === 'edit' ? { unitId: item.unitId, choice, text: edits[item.unitId] } : { unitId: item.unitId, choice };
    });
    submit({ action: 'save', title: title.trim(), items });
  }

  const changes = review
    ? review.items.filter((item) => choices[item.unitId] === 'accept' || choices[item.unitId] === 'edit').length
    : 0;
  const editsValid = review
    ? review.items.every((item) => choices[item.unitId] !== 'edit' || (edits[item.unitId] ?? '').trim())
    : false;
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
          <p className="text-sm font-medium text-cyan-400">Tailor Resume</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Reword your resume for this job</h1>
          <p className="mt-3 max-w-2xl text-slate-400">
            The lines most relevant to this job are reworded in its terms. Each suggestion is checked against its
            original line for new skills, figures and wording; the check is not exhaustive, so review each one before
            using it. The result is saved as a new resume and your original stays as it is.
          </p>
        </header>

        <section className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <label htmlFor="instructions" className="text-sm font-medium text-slate-300">
            Anything to focus on? (optional)
          </label>
          <textarea
            id="instructions"
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            maxLength={1000}
            rows={2}
            placeholder="For example: focus on my backend and API work."
            className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-slate-200"
          />
          <button
            onClick={handleStart}
            disabled={!canStart}
            className="rounded-xl bg-cyan-500 px-5 py-3 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy === 'start' ? 'Tailoring your resume… this takes about 15 seconds' : 'Tailor my resume'}
          </button>
          {run?.status === 'AWAITING_REVIEW' && (
            <p className="text-sm text-slate-500">Save or discard the current suggestions before tailoring again.</p>
          )}
        </section>

        {error && <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</p>}

        {review && (
          <section className="space-y-6 rounded-2xl border border-slate-800 bg-slate-900 p-6">
            {review.missingSkills.length > 0 && (
              <div className="rounded-xl border border-slate-700 bg-slate-950 p-4 text-sm">
                <p className="font-medium text-slate-200">Skills this job asks for that your resume doesn&apos;t show</p>
                <p className="mt-1 text-slate-400">{review.missingSkills.join(', ')}</p>
                <p className="mt-2 text-slate-500">
                  Suggestions that add one of these are flagged. Add them yourself only if you have the experience.
                </p>
              </div>
            )}

            {review.items.length === 0 && (
              <p className="text-slate-400">
                We didn&apos;t find lines that would read better for this job. Your resume already fits it well.
              </p>
            )}

            {review.items.map((item) => {
              const choice = choices[item.unitId] ?? 'keep';
              const notes = explainProblems(item.problems);
              return (
                <article key={item.unitId} className="space-y-3 rounded-xl bg-slate-950 p-5">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Original</p>
                    <p className="mt-1 leading-7 text-slate-400">{item.original}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-cyan-400">Suggested</p>
                    {item.unchanged ? (
                      <p className="mt-1 text-sm text-slate-500">No change suggested for this line.</p>
                    ) : (
                      <p className="mt-1 leading-7 text-slate-100">{item.rewritten}</p>
                    )}
                  </div>

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

                  {!item.unchanged && (
                    <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Choose what to use for this line">
                      {(Object.keys(CHOICE_LABELS) as Choice[]).map((option) => (
                        <button
                          key={option}
                          role="radio"
                          aria-checked={choice === option}
                          onClick={() => setChoices((current) => ({ ...current, [item.unitId]: option }))}
                          disabled={!!busy}
                          className={`rounded-lg border px-3 py-1.5 text-sm ${
                            choice === option
                              ? 'border-cyan-400 bg-cyan-500/15 text-cyan-200'
                              : 'border-slate-700 text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {CHOICE_LABELS[option]}
                        </button>
                      ))}
                    </div>
                  )}

                  {choice === 'edit' && (
                    <textarea
                      value={edits[item.unitId] ?? ''}
                      onChange={(event) => setEdits((current) => ({ ...current, [item.unitId]: event.target.value }))}
                      rows={3}
                      maxLength={1500}
                      className="w-full rounded-xl border border-slate-700 bg-slate-900 p-3 leading-7 text-slate-200"
                    />
                  )}
                </article>
              );
            })}

            <div className="space-y-3 border-t border-slate-800 pt-5">
              <label htmlFor="resume-title" className="text-sm font-medium text-slate-300">
                Name for the new resume
              </label>
              <input
                id="resume-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={200}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-slate-200"
              />
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={handleSave}
                  disabled={!!busy || !title.trim() || !editsValid}
                  className="rounded-xl bg-emerald-500 px-5 py-2 font-medium text-slate-950 disabled:opacity-60"
                >
                  {busy === 'decide' ? 'Saving…' : 'Save as new resume'}
                </button>
                <button
                  onClick={() => submit({ action: 'discard' })}
                  disabled={!!busy}
                  className="rounded-xl border border-red-500/40 px-5 py-2 text-red-300 disabled:opacity-60"
                >
                  Discard
                </button>
                <span className="text-sm text-slate-500">
                  {changes} of {review.items.length} line{review.items.length === 1 ? '' : 's'} will change
                </span>
              </div>
            </div>
          </section>
        )}

        {run?.status === 'COMPLETED' && run.decision?.resumeId && (
          <section className="space-y-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-6">
            <p className="text-emerald-200">
              Saved as{' '}
              <Link href={`/resumes/${run.decision.resumeId}`} className="font-medium underline">
                {run.decision.title}
              </Link>
              . Your original resume is unchanged.
            </p>
            {usingNewResume ? (
              <p className="text-sm text-slate-300">
                This application now uses the new resume. Run the analysis again to see the updated match.
              </p>
            ) : (
              <button
                onClick={() => switchToNewResume(run.decision!.resumeId!)}
                disabled={!!busy}
                className="rounded-xl border border-emerald-400/50 px-4 py-2 text-sm text-emerald-200 disabled:opacity-60"
              >
                Use it for this application
              </button>
            )}
          </section>
        )}

        {run?.status === 'REJECTED' && (
          <p className="text-sm text-slate-400">You discarded these suggestions, so nothing was saved.</p>
        )}

        {run?.status === 'FAILED' && (
          <p className="text-sm text-red-300">We couldn&apos;t finish tailoring. Please try again in a moment.</p>
        )}
      </section>
    </main>
  );
}
