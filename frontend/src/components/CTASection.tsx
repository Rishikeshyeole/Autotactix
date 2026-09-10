import { ArrowRight } from 'lucide-react';

export default function CTASection() {
  const scrollToContact = () => {
    document.getElementById('contact')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  };

  return (
    <section
      className="mx-6 mb-20 rounded-3xl px-6 py-16 text-center sm:mx-auto sm:max-w-5xl"
      style={{ backgroundColor: 'var(--accent-soft)' }}
    >
      <p
        className="text-xs font-semibold tracking-wide"
        style={{ color: 'var(--primary)' }}
      >
        GET STARTED
      </p>
      <h2
        className="mt-3 text-3xl font-extrabold sm:text-4xl"
        style={{ color: 'var(--foreground)' }}
      >
        Ready to Automate Urban Transit?
      </h2>
      <p
        className="mx-auto mt-4 max-w-xl text-base leading-relaxed"
        style={{ color: 'var(--muted-foreground)' }}
      >
        Join us in building smarter, more efficient, and more livable cities
        with the power of AI and simulation.
      </p>

      <button
        type="button"
        onClick={scrollToContact}
        className="focus-ring group mt-8 inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 ease-smooth hover:shadow-md active:scale-[0.97]"
        style={{ backgroundColor: 'var(--primary)' }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.backgroundColor = 'var(--primary-hover)')
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.backgroundColor = 'var(--primary)')
        }
      >
        Try Now
        <ArrowRight
          size={16}
          className="transition-transform duration-200 group-hover:translate-x-0.5"
        />
      </button>
    </section>
  );
}
