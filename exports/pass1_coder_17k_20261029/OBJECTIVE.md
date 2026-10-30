Implement a bounded multi-lane job pipeline in strict TypeScript under src/.

Files to create (all under src/):
- types.ts      shared interfaces: Job, JobResult, QueueOptions, BackoffOptions, BreakerOptions, TelemetryEvent
- queue.ts      a fixed-capacity ring buffer queue over a SharedArrayBuffer using Atomics on Int32 views. It MUST be usable from the main thread without blocking: provide async push/pop (Promise based, resolving on the next macrotask tick) and a synchronous tryPush. NEVER call Atomics.wait on the main thread; only worker threads may block.
- worker.ts     worker_threads entry point that reconstructs the queue over the SharedArrayBuffer sent in workerData and drains it, posting results back
- pool.ts       WorkerPool: spawns N workers, distributes jobs, terminates cleanly, exposes run(job) => Promise<JobResult>, and closes all workers on dispose()
- backoff.ts    exponential backoff with full jitter and a max delay, plus an async sleep(ms) helper
- circuit-breaker.ts  a CircuitBreaker with closed/open/half-open states, failure threshold, cooldown, and allow()/recordSuccess()/recordFailure()
- pipeline.ts   a Pipeline that composes stages, retries a failing stage with backoff, short-circuits when the circuit breaker is open, and preserves input order in its output
- telemetry.ts  an in-memory Telemetry collector with record(event) and snapshot() returning counts per event name
- index.ts      barrel exports for every module above

Rules:
- strict TypeScript, no `any`, no external runtime dependencies (node builtins only).
- No busy-wait loops and no Atomics.wait anywhere on the main thread.
- Every file must be complete and compilable; do not leave TODOs or placeholder bodies.
- `npx tsc --noEmit` must exit 0.
