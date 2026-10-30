export type BreakerState = "closed" | "open" | "half-open";

export interface BreakerOptions {
  failureThreshold: number;
  cooldownMs: number;
}

export class CircuitBreaker {
  private state: BreakerState = "closed";
  private failures = 0;
  private openedAt = 0;
  private readonly opts: BreakerOptions;

  constructor(opts: BreakerOptions) {
    this.opts = opts;
  }

  getState(): BreakerState {
    if (this.state === "open") {
      if (Date.now() - this.openedAt >= this.opts.cooldownMs) {
        this.state = "half-open";
      }
    }
    return this.state;
  }

  allow(): boolean {
    const s = this.getState();
    return s !== "open";
  }

  recordSuccess(): void {
    this.failures = 0;
    this.state = "closed";
  }

  recordFailure(): void {
    this.failures++;
    if (this.failures >= this.opts.failureThreshold) {
      this.state = "open";
      this.openedAt = Date.now();
    }
  }
}
