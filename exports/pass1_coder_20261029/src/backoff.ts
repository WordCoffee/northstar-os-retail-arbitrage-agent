export interface BackoffOptions {
  baseMs: number;
  maxMs: number;
  factor: number;
}

export function backoffDelay(attempt: number, opts: BackoffOptions): number {
  const raw = opts.baseMs * Math.pow(opts.factor, attempt);
  return Math.min(raw, opts.maxMs);
}

export async function withBackoff<T>(fn: () => Promise<T>, opts: BackoffOptions): Promise<T> {
  let attempt = 0;
  while (true) {
    try {
      return await fn();
    } catch (err) {
      attempt += 1;
      const delay = backoffDelay(attempt, opts);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}
