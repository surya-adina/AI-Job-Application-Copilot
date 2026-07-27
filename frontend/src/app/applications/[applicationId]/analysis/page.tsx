import Link from 'next/link';
import { getWorkspace } from '@/lib/api/workspace';
import { redirect } from 'next/navigation';
import { getAuthToken } from '@/lib/auth/server';


export default async function ApplicationAnalysisPage({
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
  const analysis = workspace.analysis;

  if (!analysis) {
    return (
      <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
        <section className="mx-auto max-w-4xl space-y-6">
          <Link
            href={`/applications/${applicationId}`}
            className="text-sm font-medium text-cyan-500 hover:underline"
          >
            ← Back to Application
          </Link>

          <div className="rounded-3xl border border-slate-800 bg-slate-900 p-8">
            <h1 className="text-2xl font-semibold">No analysis yet</h1>
            <p className="mt-3 text-slate-400">
              Run an analysis for this application first.
            </p>
          </div>
        </section>
      </main>
    );
  }

  const strengths = analysis.matchedSkills.slice(0, 4);
  const missingSkills = analysis.missingSkills ?? [];

  const priorities = missingSkills.slice(0, 3).map((skill, index) => ({
    rank: index + 1,
    impact: Math.max(5 - index, 3),
    title: `Add evidence for ${skill}`,
    why: `The job appears to value ${skill}, but this skill was not found in the saved resume analysis.`,
    evidence: [`Missing skill from analysis: ${skill}`],
    action: `If you genuinely have experience with ${skill}, add a concrete example in your Skills, Projects, or Experience section. If not, treat this as a growth area instead of adding it to the resume.`,
  }));

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100 md:px-10">
      <section className="mx-auto max-w-6xl space-y-8">
        <div className="mb-2">
          <Link
            href={`/applications/${applicationId}`}
            className="inline-flex text-sm font-medium text-cyan-500 hover:underline"
          >
            ← Back to Application
          </Link>
        </div>

        <header className="pt-2">
          <p className="text-sm font-medium text-cyan-400">
            AI Job Application Copilot
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">
            Resume Match Report
          </h1>
          <p className="mt-3 max-w-2xl text-slate-400">
            Real analysis generated from your resume and the selected job
            description.
          </p>
        </header>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm text-slate-400">Match Score</p>
              <div className="mt-2 flex items-end gap-3">
                <span className="text-6xl font-bold">{analysis.score}%</span>
                <span className="mb-2 rounded-full bg-emerald-500/10 px-3 py-1 text-sm font-medium text-emerald-400">
                  High Confidence
                </span>
              </div>
            </div>

            <div className="w-full md:w-80">
              <div className="h-3 rounded-full bg-slate-800">
                <div
                  className="h-3 rounded-full bg-cyan-400"
                  style={{ width: `${analysis.score}%` }}
                />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-400">
                {analysis.strengths}
              </p>
            </div>
          </div>
        </section>

        <div className="grid gap-6 md:grid-cols-2">
          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-semibold">Strengths</h2>
            <div className="mt-4 space-y-3">
              {strengths.map((skill) => (
                <div
                  key={skill}
                  className="rounded-xl bg-emerald-500/10 px-4 py-3 text-emerald-300"
                >
                  ✓ {skill}
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-semibold">Matched Skills</h2>
            <p className="mt-1 text-sm text-slate-400">
              These skills were found in your resume and matched against the job.
            </p>

            <div className="mt-4 space-y-3">
              {analysis.matchedSkills.map((skill) => (
                <div
                  key={skill}
                  className="rounded-xl bg-emerald-500/10 px-4 py-3 text-emerald-300"
                >
                  ✓ {skill}
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-semibold">Missing Skills</h2>
            <p className="mt-1 text-sm text-slate-400">
              These are gaps found by the analysis.
            </p>

            <div className="mt-4 space-y-3">
              {missingSkills.length > 0 ? (
                missingSkills.map((skill) => (
                  <div
                    key={skill}
                    className="rounded-xl bg-amber-500/10 px-4 py-3 text-amber-300"
                  >
                    • {skill}
                  </div>
                ))
              ) : (
                <div className="rounded-xl bg-emerald-500/10 px-4 py-3 text-emerald-300">
                  No major missing skills found in this analysis.
                </div>
              )}
            </div>
          </section>
        </div>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <div>
            <h2 className="text-xl font-semibold">Top Resume Priorities</h2>
            <p className="mt-1 text-sm text-slate-400">
              Focus on these first. They come from the saved AI analysis.
            </p>
          </div>

          <div className="mt-6 space-y-5">
            {priorities.length === 0 ? (
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-5">
                <h3 className="text-lg font-semibold text-emerald-300">
                  No major resume gaps found
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  The saved analysis did not identify major missing skills for this role.
                  Focus on keeping the resume truthful, clear, and specific to the role.
                </p>
              </div>
            ) : (
              priorities.map((item) => (
                <article
                  key={item.rank}
                  className="rounded-2xl border border-slate-800 bg-slate-950 p-5"
                >
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div className="flex gap-4">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-cyan-500/10 text-lg font-bold text-cyan-300">
                        {item.rank}
                      </div>

                      <div>
                        <h3 className="text-lg font-semibold">{item.title}</h3>
                        <p className="mt-2 text-sm leading-6 text-slate-400">
                          {item.why}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
                      Impact {'★'.repeat(item.impact)}
                      <span className="text-slate-700">
                        {'★'.repeat(5 - item.impact)}
                      </span>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl bg-slate-900 p-4">
                      <p className="text-sm font-medium text-slate-300">
                        Evidence
                      </p>
                      <ul className="mt-3 space-y-2 text-sm text-slate-400">
                        {item.evidence.map((point) => (
                          <li key={point}>• {point}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="rounded-xl bg-slate-900 p-4">
                      <p className="text-sm font-medium text-slate-300">Action</p>
                      <p className="mt-3 text-sm leading-6 text-slate-400">
                        {item.action}
                      </p>
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </section>
    </main>
  );
}