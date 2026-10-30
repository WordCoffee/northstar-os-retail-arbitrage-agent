import { Job, JobResult } from './types';
import { BackoffOptions } from './types';
import { BreakerOptions } from './types';
import { withBackoff } from './backoff';
import { CircuitBreaker } from './circuit-breaker';
import { TelemetryCollector } from './telemetry';

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
  private readonly telemetry: TelemetryCollector;

  constructor(options: PipelineOptions) {
    this.stages = options.stages;
    this.backoff = options.backoff;
    this.breaker = new CircuitBreaker(options.breaker);
    this.telemetry = new TelemetryCollector();
  }

  async run(job: Job): Promise<JobResult> {
    if (!this.breaker.allow()) {
      this.telemetry.record({ name: 'circuit_open', timestamp: Date.now() });
      return { id: job.id, ok: false, error: 'Circuit breaker is open' };
    }

    let current: JobResult = { id: job.id, ok: true, value: job.payload };

    for (let i = 0; i < this.stages.length; i++) {
      const stage = this.stages[i];
      const stageName = `stage_${i}`;

      try {
        const result = await withBackoff(
          () => stage(job),
          this.backoff
        );
        if (result.ok) {
          this.breaker.recordSuccess();
          this.telemetry.record({ name: `${stageName}_success`, timestamp: Date.now() });
          current = result;
        } else {
          this.breaker.recordFailure();
          this.telemetry.record({ name: `${stageName}_failure`, timestamp: Date.now() });
          return { id: job.id, ok: false, error: result.error ?? 'Stage failed' };
        }
      } catch (err) {
        this.breaker.recordFailure();
        const message = err instanceof Error ? err.message : String(err);
        this.telemetry.record({ name: `${stageName}_error`, timestamp: Date.now() });
        return { id: job.id, ok: false, error: message };
      }
    }

    return current;
  }

  get telemetry(): TelemetryCollector {
    return this.telemetry;
  }

  get breaker(): CircuitBreaker {
    return this.breaker;
  }
}