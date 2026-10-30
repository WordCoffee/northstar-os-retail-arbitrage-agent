import { workerData, parentPort } from 'worker_threads';
import { RingQueue } from './queue';
import { Job, JobResult } from './types';

interface WorkerData {
  sab: SharedArrayBuffer;
  capacity: number;
}

function processJob(job: Job): JobResult {
  try {
    const value = (job.payload as { run?: () => unknown })?.run?.();
    return { id: job.id, ok: true, value };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { id: job.id, ok: false, error: message };
  }
}

function main(): void {
  const data = workerData as WorkerData;
  const queue = RingQueue.fromSharedBuffer(data.sab, data.capacity);

  while (true) {
    const item = queue.tryPop();
    if (item === null) {
      break;
    }
    const job: Job = { id: `job-${item}`, payload: { run: () => item } };
    const result = processJob(job);
    parentPort?.postMessage(result);
  }

  parentPort?.postMessage({ type: 'drained' });
}

main();
