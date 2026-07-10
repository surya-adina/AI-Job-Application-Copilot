import Link from 'next/link';

const suggestions = [
  {
    priority: 'HIGH',
    title: 'Emphasize LLM APIs experience',
    targetSection: 'Summary',
    why: 'The job requires LLM API experience, but the current resume only mentions OpenAI APIs generally.',
    evidence: [
      'Job description lists LLM APIs as a required qualification.',
      'Resume mentions OpenAI APIs but not LLM application work clearly.',
    ],
    action:
      'If true, clarify how you used OpenAI APIs to build LLM-powered features or workflows.',
  },
  {
    priority: 'MEDIUM',
    title: 'Handle AWS as a preferred gap',
    targetSection: 'Skills',
    why: 'AWS is preferred, so it can improve competitiveness but should not be overstated.',
    evidence: [
      'AWS appears under preferred qualifications.',
      'Resume does not currently show AWS evidence.',
    ],
    action:
      'If you have real AWS experience, add it. Otherwise, focus on adjacent Docker and backend infrastructure experience.',
  },
];

export default async function ResumeReviewPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;

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

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold">Summary</h2>
          <p className="mt-3 leading-7 text-slate-400">
            Your resume shows strong backend and AI tooling experience. The main
            improvement is clarifying LLM API work and handling preferred cloud
            skills honestly.
          </p>
        </section>

        <section className="space-y-5">
          {suggestions.map((item) => (
            <article
              key={item.title}
              className="rounded-2xl border border-slate-800 bg-slate-900 p-6"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-300">
                      {item.priority}
                    </span>
                    <span className="text-sm text-slate-400">
                      {item.targetSection}
                    </span>
                  </div>

                  <h2 className="mt-3 text-xl font-semibold">{item.title}</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    {item.why}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div className="rounded-xl bg-slate-950 p-4">
                  <p className="text-sm font-medium text-slate-300">Evidence</p>
                  <ul className="mt-3 space-y-2 text-sm text-slate-400">
                    {item.evidence.map((point) => (
                      <li key={point}>• {point}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-xl bg-slate-950 p-4">
                  <p className="text-sm font-medium text-slate-300">Action</p>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    {item.action}
                  </p>
                </div>
              </div>
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}