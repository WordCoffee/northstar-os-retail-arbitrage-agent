import { Worker } from "node:worker_threads";
import { RingQueue } from "./queue";
import { Job, JobResult } from "./types";

interface Pending {
  resolve: (r: JobResult) => void;
  reject: (e: Error) => void;
}

export class WorkerPool {
  private readonly workers: Worker[] = [];
  private readonly queue: RingQueue;
  private readonly pending = new Map<number, Pending>();
  private nextIndex = 0;
  private disposed = false;

  constructor(
    workerCount: number,
    capacity: number,
    handler: (job: Job) => unknown
  ) {
    if (!Number.isInteger(workerCount) || workerCount <= 0) {
      throw new Error("workerCount must be a positive integer");
    }
    this.queue = new RingQueue(capacity);
    for (let i = 0; i < workerCount; i++) {
      const w = new Worker(require.resolve("./worker"), {
        workerData: {
          sab: this.queue.sharedBuffer,
          capacity,
          handler,
          jobs: [] as Job[],
        },
      });
      w.on("message", (msg: { type: string; result: JobResult }) => {
        if (msg.type === "result") {
          const p = this.pending.get(this.nextIndex);
          if (p) {
            this.pending.delete(this.nextIndex);
            p.resolve(msg.result);
          }
        }
      });
      w.on("error", (err: Error) => {
        for (const p of this.pending.values()) {
          p.reject(err);
        }
        this.pending.clear();
      });
      this.workers.push(w);
    }
  }

  async run(job: Job): Promise<JobResult> {
    if (this.disposed) {
      throw new Error("pool is disposed");
    }
    const idx = this.nextIndex++;
    const promise = new Promise<JobResult>((resolve, reject) => {
      this.pending.set(idx, { resolve, reject });
    });
    await this.queue.push(idx);
    return promise;
  }

  async dispose(): Promise<void> {
    if (this.disposed) return;
    this.disposed = true;
    for (const w of this.workers) {
      w.postMessage({ type: "stop" });
    }
    await Promise.all(
      this.workers.map((w) =>
        new Promise<void>((resolve) => {
          w.on("exit", () => resolve());
        })
      )
    );
  }
}
