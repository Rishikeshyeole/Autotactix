import type { ContactSubmissionResult } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined;

/**
 * Submits a visitor question about AutoTactix.
 *
 * This service is structured so that a real backend endpoint can be
 * connected later by setting VITE_API_BASE_URL. Until that endpoint
 * exists, no network request is attempted and the promise resolves
 * to a success result so the UI flow can be fully exercised.
 */
export async function submitContactQuestion(
  question: string
): Promise<ContactSubmissionResult> {
  const trimmed = question.trim();

  if (!trimmed) {
    return {
      success: false,
      message: 'Please enter your question.',
    };
  }

  try {
    if (!API_BASE_URL) {
      // No backend configured yet. Simulate the network round trip so
      // the loading/success UI states can be verified end to end.
      await wait(700);
      return {
        success: true,
        message: 'Your question has been submitted successfully.',
      };
    }

    const response = await fetch(`${API_BASE_URL}/contact`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question: trimmed }),
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    return {
      success: true,
      message: 'Your question has been submitted successfully.',
    };
  } catch (error) {
    return {
      success: false,
      message: 'Something went wrong. Please try again.',
    };
  }
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
