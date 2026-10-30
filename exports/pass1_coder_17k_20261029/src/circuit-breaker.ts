import { BreakerOptions } from './types';

export type BreakerState = 'closed' | 'open' | 'half-open';

export class CircuitBreaker {
  private state: BreakerState = 'closed';
  private failureCount = 0;
  private lastFailureTime = 0;
  private readonly options: BreakerOptions;

  constructor(options: BreakerOptions) {
    this.options = options;
  }

  getState(): BreakerState {
    return this.state;
  }

  allow(): boolean {
    if (this.state === 'closed') {
      return true;
    }
    if (this.state === 'open') {
      const elapsed = Date.now() - this.lastFailureTime;
      if (elapsed >= this.options.cooldownMs) {
        this.state = 'half-open';
        return true;
      }
      return false;
    }
    return true;
  }

  recordSuccess(): void {
    this.failureCount = 0;
    this.state = 'closed';
  }

  recordFailure(): void {
    this.failureCount += 1;
    this.lastFailureTime = Date.now();
    if (this.failureCount >= this.options.failureThreshold) {
      this.state = 'open';
    }
  }
}