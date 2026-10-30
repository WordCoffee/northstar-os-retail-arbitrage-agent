import { Worker } from 'worker_threads';
import { RingQueue } from './queue';
import { Job, JobResult } from './types';

interface PendingJob {
  job: Job;
  resolve: (r: JobResult) => void;
  reject: (e: Error) => void;
}

export class WorkerPool {
  private readonly workers: Worker[] = [];
  private readonly queue: RingQueue;
  private readonly pending: Map<number, PendingJob> = new Map();
  private nextJobIndex = 0;
  private disposed = false;

  constructor(workerCount: number, capacity: number) {
    this.queue = new RingQueue({ capacity });
    for (let i = 0; i < workerCount; i++) {
      const w = new Worker(require.resolve('./worker'), {
        workerData: {
          sab: this.queue.sharedBuffer,
          capacity,
        },
      });
      w.on('message', (msg: { type: string; result?: JobResult }) => {
        if (msg.type === 'result' && msg.result) {
          const idx = this.pending.size > 0 ? this.findPendingIndex(msg.result.id) : -1;
          if (idx >= 0) {
            const p = this.pending.get(idx);
            if (p) {
              this.pending.delete(idx);
              p.resolve(msg.result);
            }
          }
        }
      });
      w.on('error', (err: Error) => {
        for (const [, p] of this.pending) {
          p.reject(err);
        }
        this.pending.clear();
      });
      this.workers.push(w);
    }
  }

  private findPendingIndex(id: string): number {
    for (const [idx, p] of this.pending) {
      if (p.job.id === id) {
        return idx;
      }
    }
    return -1;
  }

  async run(job: Job): Promise<JobResult> {
    if (this.disposed) {
      throw new Error('Pool is disposed');
    }
    const idx = this.nextJobIndex++;
    const pending: PendingJob = {
      job,
      resolve: () => {},
      reject: () => {},
    };
    this.pending.set(idx, pending);

    const resultPromise = new Promise<JobResult>((resolve, reject) => {
      pending.resolve = resolve;
      pending.reject = reject;
    });

    await this.queue.push(idx);
    return resultPromise;
  }

  async dispose(): Promise<void> {
    if (this.disposed) return;
    this.disposed = true;
    const promises = this.workers.map((w) => new Promise<void>((resolve) => {
      w.on('exit', () => resolve());
      w.terminate();
    }));
    await Promise.all(promises);
  }
}
