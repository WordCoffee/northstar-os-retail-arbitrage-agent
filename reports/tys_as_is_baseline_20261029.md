# Ty-as-is baseline — 2026-10-29

**Label:** **ty-as-is (text persisted by harness; not a quality claim).** This is
Ty's own orchestrator and coding lane, run against the same 20 briefs. It is not
the kernel text-lane baseline and not a quality judgement of Ty's future.

**Run:** `reports/rea_probe/proj_bench_tys/20261029T053555Z/summary.json`
**Command:** `python tools/tys_bench.py --limit 20 --restart-every 5`
**Result:** **0 / 20 content-valid** · 20/20 Ty runs returned `done` · 3 coding
steps per brief.

---

## What Ty actually produced

Ty's `CodingWorkerAdapter` is explicitly told:

> “You have no tools. Use ONLY the file contents provided. If something is not
> shown, say so.”

No context files were supplied for these briefs, and the lane has no file-write
tool. The model therefore refused, correctly under its own contract:

```
I cannot produce the content of `fix.patch` because no file contents, test
output, or source code were provided in the request. I have no tools to inspect
the repository…
```

The harness persisted each step's returned text to the artifact path so the
validators could inspect it. `plan.md`, the artifact and `verification.json` are
all refusal text; none is a project artifact.

## Why this is the honest baseline

| Lane | Content valid | What happens |
|---|---|---|
| Kernel + local 27B text lane | **17/20 (0.85)** | model writes text; content validators enforce type/terms |
| Kernel + tool nodes (p11/p13/p14) | **20/20 (1.00)** | real label, canvases and MP4 tools |
| **Ty-as-is (orchestrator + coding lane)** | **0/20 (0.00)** | lane is context-bound and read-only; refuses without files |

Ty's orchestrator can plan and sequence, but its coding lane has **no tools and
no context**. A project benchmark that expects artifacts cannot be passed by a
read-only advisory lane.

## What would move it

1. Give the lane a write-capable tool loop (the kernel already provides
   `policy → plan → execute → verify → checkpoint`).
2. Pass real context files, or let the lane read them through a bounded
   inspect step.
3. Add content acceptance at the node level, not just a `done` step status.

This is exactly the gap the kernel was built to close. The 0/20 is the “before”;
the kernel text lane (17/20) and tool lane (20/20) are the measured “after” for
the same briefs.

## Gates

No Amazon. No spend. No network beyond `127.0.0.1:8080`. The worker was stopped
after the run. Ty’s default `run()` is unchanged; this baseline used explicit
steps and a harness-persisted text output.
