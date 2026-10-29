# NS-PROJ-20 live lane baseline — 2026-10-29

**Label:** **live lane baseline**, not a project result. The local 27B wrote each
node's text; the harness persisted it. Artifact existence and file format were
checked. **Content quality was not verified.**

**Run:** `reports/rea_probe/proj_bench_live/20261029T000941Z/summary.json`
**Command:** `python tools/proj_bench.py --executor live --limit 20`
**GPU:** RTX 5080 Laptop 16 GB, idle at start (89 MiB used)
**Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`, `llama-server`, 8K context,
q8_0 KV, **MTP disabled** (see stability).

---

## 1. Result

| Metric | Value |
|---|---|
| Briefs | 20 |
| Completed (artifact ≥40 bytes) | **20 / 20** |
| Valid plans | **20 / 20** |
| Evidence coverage | **1.00** |
| Operator interventions | 0 |
| Model calls | 60 |
| Node latency p50 / p95 | **6.27 s / 11.17 s** |
| Artifact format valid | **18 / 20 (0.90)** |
| Markdown-fenced artifacts | 13 |
| Binary briefs | p11 (`label.png`), p14 (`ad.mp4`) — **both invalid** |

The two format failures are honest model behaviour, not crashes:

- `p11/label.png` contains “I can't generate a binary…”. The text lane cannot
  produce a PNG.
- `p14/ad.mp4` contains text, not an MP4 container.

Thirteen text artifacts carry a Markdown fence (` ```diff `, ` ```markdown `) that
a real tool would strip before writing. The format audit counts a patch as valid
when it contains `---`/`+++`; the fence is recorded separately.

## 2. Stability — why the server config differs from the launcher

The standard launcher (`scripts/start-northstar-llm.ps1`) uses 64K context and MTP
speculative decoding. Two attempts aborted:

| Attempt | Config | Calls before abort | Complete |
|---|---|---|---|
| 1 | 8K + MTP | 46 | 6/20 |
| 2 | 8K + MTP | 49 | 8/20 |
| **3** | **8K, no MTP** | **60** | **20/20** |

Both aborts were the server closing the connection and then refusing new ones;
the process was gone. The same model completed all 60 calls with MTP disabled.
This is an operational finding for the live lane, not a benchmark failure hidden
by retries.

## 3. Thresholds set from this result

| Threshold | Value |
|---|---|
| Completion rate | ≥ **1.00** |
| Evidence coverage | ≥ **1.00** |
| Node p50 | ≤ **8.0 s** |
| Node p95 | ≤ **15.0 s** |
| Artifact format validity | ≥ **0.90** |
| Content quality | **not set** — no machine validators exist yet |

The quality threshold is deliberately unset. A file existing is not a correct
project. The next step is per-brief validators (patch contains a real hunk,
endpoint doc names a route, JSON parses, image/MP4 magic bytes, etc.) before any
quality claim is made.

## 4. What this is not

- Not a claim that Ty's full orchestrator completes projects. This is the kernel
  driving the local 27B lane and persisting its text.
- Not a quality result. 13/20 artifacts are fenced and 2/20 are impossible in a
  text-only lane.
- Not a production configuration. The launcher’s 64K+MTP mode was unstable at
  this call volume.

## 5. Gates

No Amazon. No spend. No network beyond `127.0.0.1:8080`. No vendor bundle
analysis. The worker was started locally for this run only.
