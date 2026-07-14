import CoverLetterClient from './cover-letter-client';

export default async function CoverLetterPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;

  return <CoverLetterClient applicationId={applicationId} />;
}