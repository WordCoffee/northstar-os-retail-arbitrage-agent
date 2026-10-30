`npx tsc --noEmit` in this workspace exits 2 with exactly ONE error:

src/worker.ts(26,20): error TS2769: No overload matches this call.
  Overload 1 of 2 (BigInt64Array), Overload 2 of 2 (Int32Array): Argument of type 'SharedArrayBuffer' is not assignable to parameter of type 'Int32Array'.

Line 26 is:
    Atomics.wait(queue.sharedBuffer, 0, 1, 100);

`Atomics.wait` takes a typed array and an index, not a SharedArrayBuffer. `Atomics.wait` in a worker thread is correct and must stay — the main thread must never block, but the worker may.

Fix it by constructing an Int32Array view over the shared buffer and waiting on that. Do not change anything else: not the queue, not the pool, not the pipeline, not the tsconfig, not the public API.

Reply with write_many containing ONLY src/worker.ts, complete, with the fix applied. `npx tsc --noEmit` must exit 0.
