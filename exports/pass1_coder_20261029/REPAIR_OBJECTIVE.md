The workspace already contains a complete implementation under src/. `npx tsc --noEmit` currently exits 2 with exactly these five errors:

src/pipeline.ts(2,10): error TS2459: Module '"./backoff"' declares 'BackoffOptions' locally, but it is not exported.
src/pipeline.ts(3,26): error TS2459: Module '"./circuit-breaker"' declares 'BreakerOptions' locally, but it is not exported.
src/queue.ts(29,7): error TS2540: Cannot assign to 'view' because it is a read-only property.
src/worker.ts(24,7): error TS18047: 'parentPort' is possibly 'null'.
src/worker.ts(28,5): error TS18047: 'parentPort' is possibly 'null'.

Fix every one of them by rewriting only the files that actually need to change, in a single write_many call. Rules:
- Return each changed file COMPLETE, not a diff or a fragment.
- Export the option interfaces from the modules that declare them (or import them from types.ts and re-export), so the pipeline compiles.
- Make the queue's backing view assignable (declare it mutable or construct it once in the constructor) without changing the public API.
- Narrow parentPort once at worker startup and fail fast if it is null, instead of asserting non-null at each use.
- No `any`, no ts-ignore, no placeholders, no TODOs, node builtins only.
- `npx tsc --noEmit` must exit 0 after your change.
