export interface BackoffOptions {
  baseMs: number;
  maxMs: number;
  factor: number;
}

export function sleep(ms: number): Promise<void> {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

export function backoffDelay(
  attempt: number,
  opts: BackoffOptions
): number {
  const exp = opts.baseMs * Math.pow(opts.factor, attempt);
  const capped = Math.min(exp, opts.maxMs);
  return Math.random() * capped;
}
