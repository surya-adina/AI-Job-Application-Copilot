import Link from 'next/link';
import { ThemeToggle } from '@/components/theme/theme-toggle';

const differentiators = [
  {
    title: 'Job-specific analysis',
    description:
      'Compare your resume against a selected job description and see matched skills, gaps, and fit signals.',
  },
  {
    title: 'Resume review',
    description:
      'Get targeted suggestions to improve your resume for a specific role.',
  },
  {
    title: 'Cover letter support',
    description:
      'Generate a tailored cover letter using your saved resume and job context.',
  },
  {
    title: 'Interview prep',
    description:
      'Create role-specific technical, behavioral, and project-based interview questions.',
  },
];

const workflow = [
  {
    title: 'Add resume',
    description: 'Upload or paste your current resume.',
  },
  {
    title: 'Add job',
    description: 'Paste the job description for the role you want to apply to.',
  },
  {
    title: 'Run analysis',
    description:
      'Review your match score, matched skills, missing skills, and resume guidance.',
  },
  {
    title: 'Prepare application',
    description:
      'Use resume review, cover letter, and interview prep tools before applying.',
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-background px-6 py-16 text-foreground transition-colors">
      <section className="mx-auto max-w-5xl">
        <div className="mb-20 flex items-start justify-between gap-6">
          <div>
            <p className="text-sm font-medium text-cyan-500">
              • Resume analysis        • Cover letters        • Interview prep
            </p>

            <h1 className="mt-4 text-5xl font-bold tracking-tight">
              AI Job Application Copilot
            </h1>

            <p className="mt-6 max-w-2xl text-2xl font-semibold text-muted-foreground">
              Manage job applications with AI-powered guidance.
            </p>

            <div className="mt-8 flex flex-wrap gap-4">
              <Link
                href="/register"
                className="inline-flex rounded-xl bg-cyan-500 px-6 py-3 font-semibold text-white transition hover:bg-cyan-400"
              >
                Get Started
              </Link>
            </div>
          </div>

          <ThemeToggle />
        </div>

        <section>
          <h2 className="text-3xl font-bold">What it does</h2>

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