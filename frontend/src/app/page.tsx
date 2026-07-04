import Link from 'next/link';
import { ThemeToggle } from '@/components/theme/theme-toggle';

const differentiators = [
  {
    title: 'Job-specific analysis',
    description:
      'Compares your resume against required and preferred qualifications instead of giving generic advice.',
  },
  {
    title: 'Explainable recommendations',
    description:
      'Every suggestion includes the reasoning and supporting evidence behind it.',
  },
  {
    title: 'Prioritized improvements',
    description:
      'Focus on the highest-impact changes before applying.',
  },
  {
    title: 'Progress tracking',
    description:
      'Compare resume versions and measure how your match improves over time.',
  },
];

const workflow = [
  {
    title: 'Add resume',
    description: 'Upload or paste your current resume.',
  },
  {
    title: 'Add job',
    description:
      'Paste the job description and separate required vs preferred qualifications.',
  },
  {
    title: 'Review guidance',
    description:
      'Get prioritized, evidence-backed suggestions for improving fit.',
  },
  {
    title: 'Apply smarter',
    description:
      'Use the review to improve your resume and track applications.',
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-background px-6 py-16 text-foreground transition-colors">
      <section className="mx-auto max-w-5xl">
        <div className="mb-20 flex items-start justify-between gap-6">
          <div>
            <p className="text-sm font-medium text-cyan-500">
              AI Job Application Copilot
            </p>

            <h1 className="mt-4 text-5xl font-bold tracking-tight">
              Turn job descriptions into
              <br />
              actionable resume guidance.
            </h1>

            <p className="mt-6 max-w-2xl text-lg text-muted-foreground">
              Analyze resume fit, highlight skill gaps,
              and get evidence-backed resume review suggestions.
            </p>

            <div className="mt-8">
              <Link
                href="/analysis/demo"
                className="inline-flex rounded-xl bg-cyan-500 px-6 py-3 font-semibold text-white transition hover:bg-cyan-400"
              >
                View Demo
              </Link>
            </div>
          </div>

          <ThemeToggle />
        </div>

        <section>
          <h2 className="text-3xl font-bold">Why this?</h2>

          <div className="mt-8 grid gap-6 md:grid-cols-4">
            {differentiators.map((item, index) => (
              <div key={item.title} className="rounded-2xl border p-6">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500 font-bold text-white">
                  {index + 1}
                </div>

                <h3 className="text-lg font-semibold">{item.title}</h3>

                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-20">
          <h2 className="text-3xl font-bold">How it works</h2>

          <div className="mt-8 grid gap-6 md:grid-cols-4">
            {workflow.map((item, index) => (
              <div key={item.title} className="rounded-2xl border p-6">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500 font-bold text-white">
                  {index + 1}
                </div>

                <h3 className="text-lg font-semibold">{item.title}</h3>

                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}