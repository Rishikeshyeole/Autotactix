import { useState, type FormEvent } from 'react';
import { ArrowRight } from 'lucide-react';
import { submitContactQuestion } from '../services/contactService';
import type { ContactSubmissionStatus } from '../types';

export default function ContactSection() {
  const [question, setQuestion] = useState('');
  const [status, setStatus] = useState<ContactSubmissionStatus>('idle');
  const [message, setMessage] = useState('');

  const isSubmitting = status === 'submitting';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!question.trim()) {
      setStatus('validation-error');
      setMessage('Please enter your question.');
      return;
    }

    setStatus('submitting');
    setMessage('');

    const result = await submitContactQuestion(question);

    if (result.success) {
      setStatus('success');
      setMessage(result.message);
      setQuestion('');
    } else {
      setStatus('error');
      setMessage(result.message);
    }
  };

  return (
    <section
      id="contact"
      className="py-20"
      style={{ backgroundColor: 'var(--muted)' }}
    >
      <div className="mx-auto max-w-2xl px-6 text-center">
        <p
          className="text-xs font-semibold tracking-wide"
          style={{ color: 'var(--primary)' }}
        >
          CONTACT US
        </p>
        <h2
          className="mt-3 text-3xl font-extrabold sm:text-4xl"
          style={{ color: 'var(--foreground)' }}
        >
          Have a Question About AutoTactix?
        </h2>

        <form onSubmit={handleSubmit} className="mt-8 text-left">
          <label htmlFor="question" className="sr-only">
            Your Question
          </label>
          <textarea
            id="question"
            name="question"
            value={question}
            onChange={(e) => {
              setQuestion(e.target.value);
              if (status === 'validation-error') {
                setStatus('idle');
                setMessage('');
              }
            }}
            placeholder="Your Question"
            rows={6}
            disabled={isSubmitting}
            aria-invalid={status === 'validation-error'}
            aria-describedby={message ? 'contact-form-message' : undefined}
            className="focus-ring w-full resize-none rounded-2xl border px-5 py-4 text-sm shadow-sm transition-colors duration-200"
            style={{
              backgroundColor: 'var(--card)',
              borderColor:
                status === 'validation-error'
                  ? '#e2453c'
                  : 'var(--border)',
              color: 'var(--foreground)',
            }}
          />

          {message && (
            <p
              id="contact-form-message"
              role="status"
              aria-live="polite"
              className="mt-3 text-sm font-medium"
              style={{
                color:
                  status === 'success'
                    ? 'var(--primary)'
                    : '#e2453c',
              }}
            >
              {message}
            </p>
          )}

          <div className="mt-6 flex justify-center">
            <button
              type="submit"
              disabled={isSubmitting}
              className="focus-ring inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 ease-smooth hover:shadow-md active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-70"
              style={{ backgroundColor: 'var(--primary)' }}
            >
              {isSubmitting ? 'Sending...' : 'Send Message'}
              {!isSubmitting && <ArrowRight size={16} />}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
