export interface BreakerOptions {
  threshold: number;
  resetMs: number;
}

export class CircuitBreaker {
  private failures = 0;
  private openUntil = 0;

  constructor(private opts: BreakerOptions) {}

  recordFailure(): void {
    this.failures += 1;
    if (this.failures >= this.opts.threshold) {
      this.openUntil = Date.now() + this.opts.resetMs;
    }
  }

  recordSuccess(): void {
    this.failures = 0;
    this.openUntil = 0;
  }

  isOpen(): boolean {
    return Date.now() < this.openUntil;
  }

  allow(): boolean {
    return !this.isOpen();
  }
}
