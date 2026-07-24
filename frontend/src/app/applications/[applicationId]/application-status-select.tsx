'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

const STATUSES = [
  { value: 'SAVED', label: 'Saved' },
  { value: 'APPLIED', label: 'Applied' },
  { value: 'INTERVIEWING', label: 'Interviewing' },
  { value: 'OFFER', label: 'Offer' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'WITHDRAWN', label: 'Withdrawn' },
] as const;

type ApplicationStatusSelectProps = {
  applicationId: string;
  currentStatus: string;
};

export function ApplicationStatusSelect({
  applicationId,
  currentStatus,
}: ApplicationStatusSelectProps) {
  const router = useRouter();

  const [status, setStatus] = useState(currentStatus);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  async function updateStatus(nextStatus: string) {
    setStatus(nextStatus);
    setError('');
    setIsSaving(true);

    try {
      const response = await fetch(`/api/applications/${applicationId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: nextStatus }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.message ?? 'Failed to update status');
      }

      router.refresh();
    } catch (err) {
      setStatus(currentStatus);
      setError(err instanceof Error ? err.message : 'Failed to update status');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="space-y-2">
      <label htmlFor="applicationStatus" className="text-sm font-medium">
        Application status
      </label>

      <select
        id="applicationStatus"
        value={status}
        disabled={isSaving}
        onChange={(event) => updateStatus(event.target.value)}
        className="w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {STATUSES.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>

      {isSaving ? (
        <p className="text-xs text-muted-foreground">Saving status...</p>
      ) : null}

      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
