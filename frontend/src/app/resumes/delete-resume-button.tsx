'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

type DeleteResumeButtonProps = {
  resumeId: string;
  title: string;
};

export function DeleteResumeButton({ resumeId, title }: DeleteResumeButtonProps) {
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState('');

  async function handleDelete() {
    const confirmed = window.confirm(
      `Delete resume "${title}"? Existing applications will stay saved, but this resume will be removed from your resume library.`,
    );

    if (!confirmed) {
      return;
    }

    setIsDeleting(true);
    setError('');

    try {
      const response = await fetch(`/api/resumes/${resumeId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.message ?? 'Failed to delete resume');
      }

      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete resume');
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={handleDelete}
        disabled={isDeleting}
        className="rounded-xl border border-destructive/30 px-4 py-2 text-sm font-semibold text-destructive transition hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isDeleting ? 'Deleting...' : 'Delete'}
      </button>

      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
