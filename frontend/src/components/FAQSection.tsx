import { useState } from 'react';
import { faqs } from '../data/faq';
import FAQItem from './FAQItem';

export default function FAQSection() {
  const [openId, setOpenId] = useState<string | null>(null);

  const toggle = (id: string) => {
    setOpenId((prev) => (prev === id ? null : id));
  };

  return (
    <section id="faq" className="mx-auto max-w-3xl px-6 py-20">
      <div className="text-center">
        <p
          className="text-xs font-semibold tracking-wide"
          style={{ color: 'var(--primary)' }}
        >
          FAQ
        </p>
        <h2
          className="mt-3 text-3xl font-extrabold sm:text-4xl"
          style={{ color: 'var(--foreground)' }}
        >
          Frequently Asked Questions
        </h2>
        <p
          className="mt-4 text-base"
          style={{ color: 'var(--muted-foreground)' }}
        >
          Find answers to common questions about AutoTactix.
        </p>
      </div>

      <div className="mt-10 flex flex-col gap-3">
        {faqs.map((faq) => (
          <FAQItem
            key={faq.id}
            faq={faq}
            isOpen={openId === faq.id}
            onToggle={() => toggle(faq.id)}
          />
        ))}
      </div>
    </section>
  );
}
