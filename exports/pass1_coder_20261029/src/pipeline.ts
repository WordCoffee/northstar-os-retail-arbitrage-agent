import { Job, JobResult } from './types';
import { BackoffOptions, withBackoff } from './backoff';
import { CircuitBreaker, BreakerOptions } from './circuit-breaker';
import { TelemetryEvent } from './types';

export type Stage = (job: Job) => Promise<JobResult>;

export interface PipelineOptions {
  stages: Stage[];
  backoff: BackoffOptions;
  breaker: BreakerOptions;
}

export class Pipeline {
  private readonly stages: Stage[];
  private readonly backoff: BackoffOptions;
  private readonly breaker: CircuitBreaker;

  constructor(opts: PipelineOptions) {
    this.stages = opts.stages;
    this.backoff = opts.backoff;
    this.breaker = new CircuitBreaker(opts.breaker);
  }

  async run(job: Job): Promise<JobResult> {
    if (!this.breaker.allow()) {
      return {
        id: job.id,
        ok: false,
        error: 'circuit breaker open',
      };
    }

    let current: JobResult | null = null;
    for (let i = 0; i < this.stages.length; i++) {
      const stage = this.stages[i];
      try {
        current = await withBackoff(() => stage(job), this.backoff);
        this.breaker.recordSuccess();
      } catch (err) {
        this.breaker.recordFailure();
        const message = err instanceof Error ? err.message : String(err);
        return {
          id: job.id,
          ok: false,
          error: `stage ${i} failed: ${message}`,
        };
      }
    }

    return current ?? { id: job.id, ok: false, error: 'no stages executed' };
  }

  async runOrdered(jobs: Job[]): Promise<JobResult[]> {
    const results: JobResult[] = new Array(jobs.length);
    for (let i = 0; i < jobs.length; i++) {
      results[i] = await this.run(jobs[i]);
    }
    return results;
  }
}
