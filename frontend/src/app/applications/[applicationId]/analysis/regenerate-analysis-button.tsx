'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

type RegenerateAnalysisButtonProps = {
  applicationId: string;
};

export function RegenerateAnalysisButton({
  applicationId,
}: RegenerateAnalysisButtonProps) {
  const router = useRouter();
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function regenerateAnalysis() {
    setIsRunning(true);
    setError(null);

    try {
      const response = await fetch(`/api/applications/${applicationId}/analysis`, {
        method: 'POST',
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.message ?? 'Failed to regenerate analysis');
      }

      router.refresh();
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate analysis');
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={regenerateAnalysis}
        disabled={isRunning}
        className="rounded-xl border px-4 py-2 text-sm font-semibold transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isRunning ? 'Regenerating...' : 'Regenerate Analysis'}
      </button>

      {error ? <p className="text-sm text-red-500">{error}</p> : null}
    </div>
  );
}