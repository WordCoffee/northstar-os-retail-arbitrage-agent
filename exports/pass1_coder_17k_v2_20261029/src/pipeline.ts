import { BackoffOptions, backoffDelay, sleep } from "./backoff";
import { CircuitBreaker, BreakerOptions } from "./circuit-breaker";
import { Job, JobResult } from "./types";

export type Stage = (job: Job) => Promise<unknown>;

export interface PipelineOptions {
  stages: Stage[];
  maxRetries: number;
  backoff: BackoffOptions;
  breaker: BreakerOptions;
}

export class Pipeline {
  private readonly stages: Stage[];
  private readonly maxRetries: number;
  private readonly backoff: BackoffOptions;
  private readonly breaker: CircuitBreaker;

  constructor(opts: PipelineOptions) {
    this.stages = opts.stages;
    this.maxRetries = opts.maxRetries;
    this.backoff = opts.backoff;
    this.breaker = new CircuitBreaker(opts.breaker);
  }

  async run(job: Job): Promise<JobResult> {
    let current: unknown = job.payload;
    for (let i = 0; i < this.stages.length; i++) {
      const stage = this.stages[i];
      let attempt = 0;
      let ok = false;
      let value: unknown = undefined;
      let errMsg: string | undefined;

      while (attempt <= this.maxRetries) {
        if (!this.breaker.allow()) {
          return { id: job.id, ok: false, value: null, error: "circuit breaker open" };
        }
        try {
          value = await stage({ ...job, payload: current });
          this.breaker.recordSuccess();
          ok = true;
          break;
        } catch (e) {
          errMsg = e instanceof Error ? e.message : String(e);
          this.breaker.recordFailure();
          attempt++;
          if (attempt <= this.maxRetries) {
            const delay = backoffDelay(attempt - 1, this.backoff);
            await sleep(delay);
          }
        }
      }

      if (!ok) {
        return { id: job.id, ok: false, value: null, error: errMsg ?? "stage failed" };
      }
      current = value;
    }
    return { id: job.id, ok: true, value: current };
  }
}
