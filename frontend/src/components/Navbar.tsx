import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import logo from '../assets/logo/autotactix-logo.svg';
import type { Theme } from '../types';

interface NavbarProps {
  theme: Theme;
  onToggleTheme: () => void;
}

const NAV_LINKS = [
  { label: 'Home', href: 'home' },
  { label: 'Features', href: 'features' },
  { label: 'FAQ', href: 'faq' },
  { label: 'Contact', href: 'contact' },
];

export default function Navbar({ theme, onToggleTheme }: NavbarProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const scrollToSection = (id: string) => {
    setIsMobileMenuOpen(false);
    if (id === 'home') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    const el = document.getElementById(id);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <header
      className="sticky top-0 z-50 border-b"
      style={{
        backgroundColor: 'var(--background)',
        borderColor: 'var(--border)',
      }}
    >
      <nav
        className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6"
        aria-label="Main navigation"
      >
        <button
          type="button"
          onClick={() => scrollToSection('home')}
          className="focus-ring flex items-center gap-2 rounded-md"
          aria-label="AutoTactix — go to home"
        >
          <img src={logo} alt="" className="h-7 w-7" aria-hidden="true" />
          <span className="text-base font-bold" style={{ color: 'var(--foreground)' }}>
            AutoTactix
          </span>
        </button>

        <ul className="hidden items-center gap-8 md:flex">
          {NAV_LINKS.map((link) => (
            <li key={link.href}>
              <button
                type="button"
                onClick={() => scrollToSection(link.href)}
                className="focus-ring rounded-md text-sm font-medium transition-colors duration-200 hover:opacity-100"
                style={{ color: 'var(--muted-foreground)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--primary)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--muted-foreground)')}
              >
                {link.label}
              </button>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-3">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button
            type="button"
            className="focus-ring rounded-md p-1.5 md:hidden"
            aria-label={isMobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={isMobileMenuOpen}
            aria-controls="mobile-menu"
            onClick={() => setIsMobileMenuOpen((prev) => !prev)}
          >
            {isMobileMenuOpen ? (
              <X size={22} style={{ color: 'var(--foreground)' }} />
            ) : (
              <Menu size={22} style={{ color: 'var(--foreground)' }} />
            )}
          </button>
        </div>
      </nav>

      {isMobileMenuOpen && (
        <div
          id="mobile-menu"
          className="border-t px-6 py-4 md:hidden"
          style={{ borderColor: 'var(--border)', backgroundColor: 'var(--background)' }}
        >
          <ul className="flex flex-col gap-4">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <button
                  type="button"
                  onClick={() => scrollToSection(link.href)}
                  className="focus-ring w-full rounded-md text-left text-sm font-medium"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  {link.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </header>
  );
}
