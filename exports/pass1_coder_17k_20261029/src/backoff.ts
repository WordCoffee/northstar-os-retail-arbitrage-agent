import { BackoffOptions } from './types';

export function sleep(ms: number): Promise<void> {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

export function computeDelay(attempt: number, options: BackoffOptions): number {
  const base = options.baseMs;
  const max = options.maxMs;
  const exponential = base * Math.pow(2, attempt);
  const jitter = Math.random() * exponential;
  return Math.min(jitter, max);
}

export async function withBackoff<T>(
  fn: () => Promise<T>,
  options: BackoffOptions
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < options.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (attempt < options.maxAttempts - 1) {
        const delay = computeDelay(attempt, options);
        await sleep(delay);
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}