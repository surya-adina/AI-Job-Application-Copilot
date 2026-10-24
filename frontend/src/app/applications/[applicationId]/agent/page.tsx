import AgentClient from './agent-client';

export default async function AgentPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;

  return <AgentClient applicationId={applicationId} />;
}
