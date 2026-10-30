import { Worker } from 'worker_threads';
import { RingQueue } from './queue';
import { Job, JobResult } from './types';

interface PendingJob {
  job: Job;
  resolve: (result: JobResult) => void;
  reject: (err: Error) => void;
}

export class WorkerPool {
  private readonly workers: Worker[] = [];
  private readonly queue: RingQueue;
  private readonly pending: Map<string, PendingJob> = new Map();
  private nextJobId = 0;
  private disposed = false;

  constructor(workerCount: number, capacity: number) {
    this.queue = new RingQueue({ capacity });
    for (let i = 0; i < workerCount; i++) {
      const worker = new Worker(require.resolve('./worker'), {
        workerData: {
          sab: this.queue.sharedBuffer,
          capacity,
        },
      });
      worker.on('message', (msg: JobResult | { type: string }) => {
        if (typeof msg === 'object' && msg !== null && 'id' in msg) {
          const result = msg as JobResult;
          const pending = this.pending.get(result.id);
          if (pending) {
            this.pending.delete(result.id);
            pending.resolve(result);
          }
        }
      });
      worker.on('error', (err: Error) => {
        for (const [, p] of this.pending) {
          p.reject(err);
        }
        this.pending.clear();
      });
      this.workers.push(worker);
    }
  }

  async run(job: Job): Promise<JobResult> {
    if (this.disposed) {
      throw new Error('Pool is disposed');
    }
    const id = `job-${this.nextJobId++}`;
    const wrappedJob: Job = { id, payload: job.payload };

    const promise = new Promise<JobResult>((resolve, reject) => {
      this.pending.set(id, { job: wrappedJob, resolve, reject });
    });

    const encoded = this.encodeJob(wrappedJob);
    await this.queue.push(encoded);
    return promise;
  }

  private encodeJob(job: Job): number {
    const hash = job.id.length;
    return hash;
  }

  async dispose(): Promise<void> {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    const exits: Promise<void>[] = this.workers.map((w) =>
      new Promise<void>((resolve) => {
        w.on('exit', () => resolve());
        w.terminate();
      })
    );
    await Promise.all(exits);
    this.workers.length = 0;
  }

  get size(): number {
    return this.workers.length;
  }
}