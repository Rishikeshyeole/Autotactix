import { Plus } from 'lucide-react';
import type { FAQ } from '../types';

interface FAQItemProps {
  faq: FAQ;
  isOpen: boolean;
  onToggle: () => void;
}

export default function FAQItem({ faq, isOpen, onToggle }: FAQItemProps) {
  const panelId = `faq-panel-${faq.id}`;
  const buttonId = `faq-button-${faq.id}`;

  return (
    <div
      className="rounded-2xl border transition-colors duration-200"
      style={{ borderColor: 'var(--border)', backgroundColor: 'var(--card)' }}
    >
      <h3>
        <button
          type="button"
          id={buttonId}
          aria-expanded={isOpen}
          aria-controls={panelId}
          onClick={onToggle}
          className="focus-ring flex w-full items-center justify-between gap-4 rounded-2xl px-6 py-4 text-left text-sm font-medium sm:text-base"
          style={{ color: 'var(--foreground)' }}
        >
          <span>{faq.question}</span>
          <Plus
            size={18}
            className="shrink-0 transition-transform duration-300 ease-smooth"
            style={{
              color: 'var(--primary)',
              transform: isOpen ? 'rotate(135deg)' : 'rotate(0deg)',
            }}
            aria-hidden="true"
          />
        </button>
      </h3>
      <div
        id={panelId}
        role="region"
        aria-labelledby={buttonId}
        className="grid overflow-hidden transition-all duration-300 ease-smooth"
        style={{
          gridTemplateRows: isOpen ? '1fr' : '0fr',
          opacity: isOpen ? 1 : 0,
        }}
      >
        <div className="min-h-0">
          <p
            className="px-6 pb-5 text-sm leading-relaxed"
            style={{ color: 'var(--muted-foreground)' }}
          >
            {faq.answer}
          </p>
        </div>
      </div>
    </div>
  );
}
