import logo from '../assets/logo/autotactix-logo.svg';

const FOOTER_LINKS = [
  { label: 'Home', href: 'home' },
  { label: 'Features', href: 'features' },
  { label: 'FAQ', href: 'faq' },
  { label: 'Contact', href: 'contact' },
];

export default function Footer() {
  const scrollToSection = (id: string) => {
    if (id === 'home') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    document.getElementById(id)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  };

  return (
    <footer
      className="border-t py-8"
      style={{ borderColor: 'var(--border)', backgroundColor: 'var(--background)' }}
    >
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-6 sm:flex-row">
        <button
          type="button"
          onClick={() => scrollToSection('home')}
          className="focus-ring flex items-center gap-2 rounded-md"
          aria-label="AutoTactix — go to home"
        >
          <img src={logo} alt="" className="h-6 w-6" aria-hidden="true" />
          <span
            className="text-base font-bold"
            style={{ color: 'var(--foreground)' }}
          >
            AutoTactix
          </span>
        </button>

        <ul className="flex flex-wrap items-center justify-center gap-6">
          {FOOTER_LINKS.map((link) => (
            <li key={link.href}>
              <button
                type="button"
                onClick={() => scrollToSection(link.href)}
                className="focus-ring rounded-md text-sm font-medium"
                style={{ color: 'var(--muted-foreground)' }}
              >
                {link.label}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </footer>
  );
}
