'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';

type ApplicationNotesEditorProps = {
  applicationId: string;
  initialNotes: string | null;
};

export function ApplicationNotesEditor({
  applicationId,
  initialNotes,
}: ApplicationNotesEditorProps) {
  const router = useRouter();

  const [notes, setNotes] = useState(initialNotes ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setIsSaving(true);
    setMessage('');
    setError('');

    try {
      const response = await fetch(`/api/applications/${applicationId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          notes: notes.trim(),
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.message ?? 'Failed to save notes');
      }

      setMessage('Notes saved');
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save notes');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label htmlFor="applicationNotes" className="text-sm text-muted-foreground">
          Notes
        </label>

        <textarea
          id="applicationNotes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          className="mt-2 min-h-[120px] w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
          placeholder="Add notes about this application..."
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={isSaving}
          className="rounded-xl bg-foreground px-4 py-2 text-sm font-semibold text-background transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSaving ? 'Saving...' : 'Save notes'}
        </button>

        {message ? <p className="text-xs text-emerald-500">{message}</p> : null}
        {error ? <p className="text-xs text-destructive">{error}</p> : null}
      </div>
    </form>
  );
}
