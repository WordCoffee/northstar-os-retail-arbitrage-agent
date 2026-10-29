# NS-PROJ-20 live text-lane baseline — 2026-10-29

**Label:** **live text-lane baseline**, not a quality claim and not a project
result. The local 27B wrote each node's text; the harness persisted it. Content
checks are separate and are reported honestly.

**GPU:** RTX 5080 Laptop 16 GB, idle at start (89 MiB used).
**Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`, `llama-server`, 8K context,
q8_0 KV, **MTP off** (pinned; see §4).
**Runs:** 3 × 20 briefs × 3 nodes = 180 model calls.

---

## 1. Run-to-run result

| Metric | Run 1 | Run 2 | Run 3 | Spread | Threshold |
|---|---|---|---|---|---|
| Completion (file existence) | 20/20 | 20/20 | 20/20 | 1.00 | ≥ 1.00 |
| Completion (content-enforced) | 17/20 | — | — | 0.85 | ≥ **0.85** |
| Evidence coverage | 1.00 | 1.00 | 1.00 | 1.00 | ≥ 1.00 |
| Node p50 | 6.27 s | 4.82 s | 6.11 s | 4.82–6.27 | ≤ **7.5 s** |
| Node p95 | 11.17 s | 14.08 s | 11.97 s | 11.17–14.08 | ≤ **16.9 s** |
| Format valid | 0.90 | 0.90 | 0.90 | 0.90 | ≥ **0.90** |
| Content valid (text lane) | 0.85 | 0.85 | 0.85 | 0.85 | ≥ **0.85** |

Thresholds are set from the spread: `max + 20%` for latency, observed minimum for
rates. They are baseline thresholds, not targets.

The stable text-lane content failures are **p11** (label), **p13** (social JSON)
and **p14** (ad). They are structural: a text-only lane cannot produce a PNG or an
MP4, and the social JSON does not match the documented canvas schema.

## 2. Fence handling — strip at persistence

**Decision:** strip a complete Markdown fence at persistence, and record the
event in the node's model call (`fence_stripped: true`). A partial fence is left
alone and recorded as not stripped.

- Baseline run 1 had **13 fenced artifacts**.
- Those **13 nodes were rerun** with the same prompt and config.
- After the rerun: **0 fenced**, format validity still **18/20** because p11/p14
  are not real binary formats.
- Runs 2 and 3 used the same stripping; their format rate is also 0.90.

This is a harness normalization of a transport wrapper, not a model-quality
change.

## 3. Content validators

Built in `tools/content_validators.py` using existing instruments:

| Kind | Instrument | Check |
|---|---|---|
| label | `text_fidelity` + `package_readiness` | PNG magic, OCR terms, prepress printable |
| ad | `ffprobe` | video + audio, 12–15 s, 1080×1920 |
| A+ | `specRegistry.js` | at least 3 module ids named |
| patch | regex | `---`/`+++` and a hunk |
| JSON | parser | parses after fence strip |
| social | documented canvas sizes | format + width/height |
| text | length + required terms | minimum content and named terms |

Quality was measured **only after** these ran on the baseline artifacts. The
text-lane rate is **17/20 (0.85)** on every run; p11, p13, p14 fail.

## 4. MTP off — pinned setting

| Config | Calls before abort | Complete |
|---|---|---|
| 8K + MTP | 46 | 6/20 |
| 8K + MTP | 49 | 8/20 |
| **8K, no MTP** | **60** | **20/20** |

The 64K + MTP launcher also aborted earlier. **MTP off, 8K context, q8_0 KV** is
recorded as the baseline setting because it is the only configuration that
completed 60 calls without a server exit.

## 5. Tool lane — p11 and p14

The two invalid binary artifacts were routed through tool nodes on run 1:

| Brief | Before | After | Valid | Why |
|---|---|---|---|---|
| p11 `label.png` | 2,737 B text | 1,965,681 B PNG | **yes** | `pouch_label.compose` produced a real label; OCR terms read; prepress printable |
| p14 `ad.mp4` | 1,217 B text | 2,737,719 B MP4 | **yes** | 12.0 s, 1080×1920, video + audio (FFmpeg probe) |
| p13 `canvases.json` | 406 B text | 692 B JSON | **yes** | `presets.js` via Node emitted the five documented format/width/height rows |

Tool-lane content after the rerun: **20/20 (1.00)**. Format after tool: **20/20**.
The text-lane baseline metrics above are unchanged; the tool lane is a separate
capability, not a retroactive baseline.

## 6. Enforced-validator run

The content validators are now registered in `agent_kernel/verify.py`, so a node
cannot be `done` on file existence alone. A full enforced run (5 server restarts,
4 briefs per server) produced:

| Metric | Value |
|---|---|
| Complete | **17 / 20** |
| Evidence coverage | **0.95** |
| p50 / p95 | **5.08 s / 12.90 s** |
| Failing briefs | **p11 (label), p13 (social), p14 (ad)** |
| Tool lane on the same run | **20 / 20 content-valid** |

This is the meaningful text-lane baseline: 17/20 projects pass content validation;
the three failures are structural and are solved by tool nodes, not more text.

## 7. What this is not

- Not a quality claim. “Content valid” means the artifact is the right type and
  carries the required terms/streams; it does not judge prose or design.
- Not Ty's full orchestrator. The kernel drove the local 27B lane.
- Not a production configuration. MTP is disabled for stability.
- Not a claim that the two binary briefs are solved in the text lane; they
  require tool nodes.

## 7. Gates

No Amazon. No spend. No network beyond `127.0.0.1:8080`. No vendor bundle
analysis. The worker was stopped after the runs; GPU returned to 89 MiB.
