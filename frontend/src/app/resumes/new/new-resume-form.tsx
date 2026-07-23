'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';

type Mode = 'upload' | 'paste';

export function NewResumeForm() {
  const router = useRouter();

  const [mode, setMode] = useState<Mode>('upload');
  const [title, setTitle] = useState('');
  const [rawText, setRawText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function handleUpload() {
    if (!file) {
      throw new Error('Choose a PDF, DOCX, or TXT resume file');
    }

    const formData = new FormData();
    formData.append('file', file);

    if (title.trim()) {
      formData.append('title', title.trim());
    }

    const response = await fetch('/api/resumes/upload', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.message ?? 'Failed to upload resume');
    }
  }

  async function handlePaste() {
    const response = await fetch('/api/resumes', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title, rawText }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.message ?? 'Failed to save resume');
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      if (mode === 'upload') {
        await handleUpload();
      } else {
        await handlePaste();
      }

      router.push('/resumes');
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save resume');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="flex rounded-2xl border bg-background p-1">
        <button
          type="button"
          onClick={() => setMode('upload')}
          className={`flex-1 rounded-xl px-4 py-3 text-sm font-semibold transition ${
            mode === 'upload'
              ? 'bg-foreground text-background'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Upload file
        </button>
        <button
          type="button"
          onClick={() => setMode('paste')}
          className={`flex-1 rounded-xl px-4 py-3 text-sm font-semibold transition ${
            mode === 'paste'
              ? 'bg-foreground text-background'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Paste text
        </button>
      </div>

      <div>
        <label htmlFor="title" className="text-sm font-medium">
          Resume title
        </label>
        <input
          id="title"
          type="text"
          required={mode === 'paste'}
          minLength={mode === 'paste' ? 2 : undefined}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          className="mt-2 w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
          placeholder="Software Engineer Resume"
        />
        {mode === 'upload' ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Optional. If empty, we will use the file name.
          </p>
        ) : null}
      </div>

      {mode === 'upload' ? (
        <div>
          <label htmlFor="resumeFile" className="text-sm font-medium">
            Resume file
          </label>
          <input
            id="resumeFile"
            type="file"
            required
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
            }}
            className="mt-2 w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
          />
          <p className="mt-2 text-xs text-muted-foreground">
            Supported formats: PDF, DOCX, TXT. Maximum size: 5 MB.
          </p>
        </div>
      ) : (
        <div>
          <label htmlFor="rawText" className="text-sm font-medium">
            Resume text
          </label>
          <textarea
            id="rawText"
            required
            minLength={20}
            value={rawText}
            onChange={(event) => setRawText(event.target.value)}
            className="mt-2 min-h-[360px] w-full rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-foreground/20"
            placeholder="Paste your resume text here..."
          />
        </div>
      )}

      {error ? (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-xl bg-foreground px-5 py-3 text-sm font-semibold text-background transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? 'Saving resume...' : 'Save resume'}
      </button>
    </form>
  );
}