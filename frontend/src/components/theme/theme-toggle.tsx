'use client';

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="h-10 w-20 rounded-xl border" />;
  }

  const isDark = resolvedTheme === 'dark';
  const nextTheme = isDark ? 'light' : 'dark';

  return (
    <button
      onClick={() => setTheme(nextTheme)}
      title={`Switch to ${nextTheme} mode`}
      className="flex items-center gap-2 rounded-xl border bg-background px-4 py-2 text-lg transition hover:scale-105"
    >
      <span>🌞</span>
      <span className="text-sm text-muted-foreground">⇄</span>
      <span>🌙</span>
    </button>
  );
}