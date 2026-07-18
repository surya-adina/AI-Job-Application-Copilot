'use client';

import { useTheme } from 'next-themes';

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  const isDark = resolvedTheme === 'dark';

  return (
    <button
      type="button"
      suppressHydrationWarning
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className="rounded-full border px-4 py-2 text-sm font-medium transition hover:bg-muted"
      aria-label="Toggle theme"
    >
      <span suppressHydrationWarning>{isDark ? '🌞 Light' : '🌙 Dark'}</span>
    </button>
  );
}