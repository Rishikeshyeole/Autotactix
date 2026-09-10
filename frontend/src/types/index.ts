import type { LucideIcon } from 'lucide-react';

export type Theme = 'light' | 'dark';

export interface Feature {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
}

export interface FAQ {
  id: string;
  question: string;
  answer: string;
}

export type ContactSubmissionStatus =
  | 'idle'
  | 'submitting'
  | 'success'
  | 'error'
  | 'validation-error';

export interface ContactSubmissionResult {
  success: boolean;
  message: string;
}
