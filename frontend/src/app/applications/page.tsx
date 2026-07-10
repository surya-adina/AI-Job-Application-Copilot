import Link from 'next/link';

const applications = [
  {
    id: '1',
    company: 'OpenAI',
    role: 'Applied AI Engineer',
    status: 'Analysis Ready',
    score: 84,
  },
  {
    id: '2',
    company: 'Anthropic',
    role: 'Software Engineer',
    status: 'Needs Analysis',
    score: null,
  },
];

export default function ApplicationsPage() {
  return (
    <main className="min-h-screen bg-background px-6 py-10 text-foreground">
      <section className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-cyan-500">
              Applications
            </p>

            <h1 className="mt-2 text-4xl font-bold">
              Job Applications
            </h1>
          </div>
        </div>

        <div className="mt-10 space-y-5">
          {applications.map((application) => (
            <Link
              key={application.id}
              href={`/applications/${application.id}`}
              className="block rounded-2xl border p-6 transition hover:border-cyan-500"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold">
                    {application.company}
                  </h2>

                  <p className="mt-2 text-muted-foreground">
                    {application.role}
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-sm text-muted-foreground">
                    {application.status}
                  </p>

                  {application.score !== null && (
                    <p className="mt-2 text-3xl font-bold text-cyan-500">
                      {application.score}%
                    </p>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}