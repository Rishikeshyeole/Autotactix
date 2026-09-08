import { Sun, Moon } from 'lucide-react';
import type { Theme } from '../types';

interface ThemeToggleProps {
  theme: Theme;
  onToggle: () => void;
}

export default function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={onToggle}
      className="focus-ring relative flex h-8 w-16 items-center rounded-full border p-1 transition-colors duration-300"
      style={{
        backgroundColor: 'var(--muted)',
        borderColor: 'var(--border)',
      }}
    >
      <Sun
        size={13}
        className="absolute left-1.5"
        style={{ color: isDark ? 'var(--muted-foreground)' : '#f4b400' }}
      />
      <Moon
        size={13}
        className="absolute right-1.5"
        style={{ color: isDark ? '#cfd8e3' : 'var(--muted-foreground)' }}
      />
      <span
        className="z-10 h-6 w-6 rounded-full shadow-sm transition-transform duration-300 ease-smooth"
        style={{
          backgroundColor: 'var(--primary)',
          transform: isDark ? 'translateX(32px)' : 'translateX(0)',
        }}
      />
    </button>
  );
}
