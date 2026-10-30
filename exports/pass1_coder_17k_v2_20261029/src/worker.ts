import { parentPort, workerData } from "node:worker_threads";
import { RingQueue } from "./queue";
import { Job, JobResult } from "./types";

const sab = workerData.sab as SharedArrayBuffer;
const capacity = workerData.capacity as number;
const queue = new RingQueue(capacity);

let running = true;

function processJob(index: number): JobResult {
  const job = workerData.jobs[index] as Job;
  try {
    const value = workerData.handler(job);
    return { id: job.id, ok: true, value };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { id: job.id, ok: false, value: null, error: msg };
  }
}

function drain(): void {
  const view = new Int32Array(queue.sharedBuffer);
  while (running) {
    const idx = queue.tryPop();
    if (idx === null) {
      Atomics.wait(view, 0, 1, 100);
      continue;
    }
    const result = processJob(idx);
    parentPort?.postMessage({ type: "result", result });
  }
}

parentPort?.on("message", (msg: { type: string }) => {
  if (msg.type === "stop") {
    running = false;
  }
});

drain();
