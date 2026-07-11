import ResumeReviewClient from './resume-review-client';

export default async function ResumeReviewPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;

  return <ResumeReviewClient applicationId={applicationId} />;
}