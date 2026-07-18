import InterviewPrepClient from './interview-prep-client';

export default async function InterviewPrepPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;

  return <InterviewPrepClient applicationId={applicationId} />;
}