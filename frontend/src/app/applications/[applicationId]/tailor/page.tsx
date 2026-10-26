import TailorClient from './tailor-client';

export default async function TailorPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;

  return <TailorClient applicationId={applicationId} />;
}
