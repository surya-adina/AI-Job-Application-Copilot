const strengths = ['FastAPI', 'PostgreSQL', 'AI evaluation', 'Prompt versioning'];

const growthAreas = ['AWS', 'Production AI infrastructure'];

const priorities = [
  {
    rank: 1,
    impact: 5,
    title: 'Highlight FastAPI architecture work',
    why: 'The target role emphasizes backend API design, and your resume already shows relevant FastAPI experience.',
    evidence: [
      'Resume mentions FastAPI and backend engineering.',
      'Job description values production AI and backend systems.',
      'Current resume does not explain architecture decisions clearly.',
    ],
    action:
      'If true, describe how you structured routes, validation, services, or database access in your FastAPI work.',
  },
  {
    rank: 2,
    impact: 4,
    title: 'Strengthen PostgreSQL impact',
    why: 'PostgreSQL is a strong match, but the resume would be stronger if it showed depth.',
    evidence: [
      'Resume includes PostgreSQL.',
      'Job description expects production-grade backend systems.',
    ],
    action:
      'If applicable, mention schema design, query optimization, indexing, or reliability improvements using real examples.',
  },
  {
    rank: 3,
    impact: 3,
    title: 'Handle AWS honestly',
    why: 'AWS is a gap for this role, but adding unsupported experience would hurt trust.',
    evidence: [
      'Job description asks for AWS.',
      'Resume does not currently show AWS evidence.',
    ],
    action:
      'If you have real AWS experience, describe it. If not, focus on adjacent strengths like Docker, deployment, or backend infrastructure.',
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
      <section className="mx-auto max-w-6xl space-y-8">
        <header>
          <p className="text-sm font-medium text-cyan-400">
            AI Job Application Copilot
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">
            Resume Match Report
          </h1>
          <p className="mt-3 max-w-2xl text-slate-400">
            Analyze a resume against a job description, identify gaps, and get
            truthful resume improvement guidance.
          </p>
        </header>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm text-slate-400">Match Score</p>
              <div className="mt-2 flex items-end gap-3">
                <span className="text-6xl font-bold">84%</span>
                <span className="mb-2 rounded-full bg-emerald-500/10 px-3 py-1 text-sm font-medium text-emerald-400">
                  High Confidence
                </span>
              </div>
            </div>

            <div className="w-full md:w-80">
              <div className="h-3 rounded-full bg-slate-800">
                <div className="h-3 w-[84%] rounded-full bg-cyan-400" />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-400">
                Strong backend and AI tooling overlap, with some cloud
                infrastructure gaps.
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
            <h2 className="text-xl font-semibold">Growth Areas</h2>
            <div className="mt-4 space-y-3">
              {growthAreas.map((skill) => (
                <div
                  key={skill}
                  className="rounded-xl bg-amber-500/10 px-4 py-3 text-amber-300"
                >
                  ⚠ {skill}
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <div>
            <h2 className="text-xl font-semibold">Top 3 Resume Priorities</h2>
            <p className="mt-1 text-sm text-slate-400">
              Focus on these first. They have the highest expected impact on this
              application.
            </p>
          </div>

          <div className="mt-6 space-y-5">
            {priorities.map((item) => (
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
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}