'use client';

import { useRouter } from 'next/navigation';
import { useState, type MouseEvent } from 'react';

type DeleteApplicationButtonProps = {
  applicationId: string;
  company: string;
  role: string;
};

export function DeleteApplicationButton({ applicationId, company, role }: DeleteApplicationButtonProps) {
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState('');

  async function handleDelete(event: MouseEvent<HTMLButtonElement>) {
    // The button sits on a clickable card; keep the click from opening the application.
    event.preventDefault();
    event.stopPropagation();

    if (!window.confirm(`Delete the application for ${role} at ${company}? This cannot be undone.`)) {
      return;
    }

    setIsDeleting(true);
    setError('');

    try {
      const response = await fetch(`/api/applications/${applicationId}`, { method: 'DELETE' });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.message ?? 'Failed to delete application');
      }

      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete application');
      setIsDeleting(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={handleDelete}
        disabled={isDeleting}
        aria-label={`Delete application for ${role} at ${company}`}
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive focus-visible:outline-2 focus-visible:outline-destructive disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isDeleting ? 'Deleting…' : 'Delete'}
      </button>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
