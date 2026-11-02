# DeepSeek-authored, Ty-supervised repair — 3 of 3 accepted (2026-11-01)

The two remaining defects are fixed and committed, and the learning store is live.
The learning *measurement* is negative: the pattern hint did not improve the local
lane on this sample. Everything below is measured, not projected.

---

## 1. AUTHOR LANE

| | |
|---|---|
| Author | **DeepSeek V4.1 Flash**, through the operator's OpenCode Go session |
| Transport | the operator session itself — **0 API requests**, **0 spend** |
| Supervisor | `qwen3.5:4b` local, unchanged (scope, probes, regression, commit, rollback) |
| Handoff | `scripts/author_lane.py`, `--author-open` / `--author-close` |
| Per-task latency | ≈ 1 min open→close (commit timestamps 23:31 and 23:32 local) |

**Deliberate deviation, stated plainly.** The directive asked for the runner to call
`opencode-go:deepseek-v4.1-flash` over the network. The OpenCode auth store does hold
an `openrouter` credential, but any programmatic call is per-token spend on the
operator's account, and this directive says *no new spend; if the lane requires payment,
stop and report; do not substitute silently*. So the lane was wired as a
**supervisor-controlled two-phase handoff**: the author writes, and the supervisor takes
the baseline, audits the changed-path set against the contract, runs the independent
probe, commits task-only bytes, or restores byte-for-byte. No model call was made and
nothing was substituted.

The handoff shows the author only the task objective, write scope, permitted read scope,
acceptance commands and commit paths — no supervisor internals, policy files,
evaluators, rollback code or ledger.

---

## 2. QUEUE RESULTS

| Task | Edits | Self-revisions the author caught | Probe | Commit |
|---|---:|---|---|---|
| `ty-artifact-jpeg` | 1 | missing-file/short-file safety; EOI searched in the last 64 bytes for trailing padding; `.JPG` via lowercased suffix | `FAIL (2)` → **PASS** | **`9e8e2cdb`** |
| `ty-diff-select-headers` | 1 | header emitted once per file, not per hunk; empty selection returns `""`; multi-file diffs keep each hunk with its own header | `FAIL (2)` → **PASS** | **`e1585917`** |
| `ty-hitl-skip-report` (earlier, local lane) | 1 | re-read after edit to confirm the return | `FAIL (1)` → **PASS** | **`883a7fed`** |

All three commits are **task-only** (`artifacts.py`, `diff.py`, `hitl_counts.py`;
+14, +42/−3, +7/−7). The supervisor's scope audit ran before every commit; no
out-of-scope path appeared. `t5`, `t6`, `t7` all pass at HEAD.

**Qualification: 3 of 3.**

---

## 3. LEARNING

### Store (append-only, `state/fix_patterns/`)

Three full trajectories recorded — reads, edit attempts, self-revision points, final
AST shape, probe transition, commit:

```text
silent-skip-counter.jsonl        ty-hitl-skip-report   accepted  883a7fed
classifier-missing-branch.jsonl  ty-artifact-jpeg      accepted  9e8e2cdb
fragment-loses-context.jsonl     ty-diff-select-headers accepted  e1585917
```

### Cold vs pattern-informed (3 fresh fixtures × 2, local lane, 32.4 s)

| Arm | Behavioural pass | Mean steps | Protocol errors |
|---|---:|---:|---:|
| Cold | **1 / 3** | 5.33 | 0 |
| Pattern-informed | **0 / 3** | 8.00 | 0 |

**Delta: −1 pass, +2.67 steps. No measurable improvement — the informed arm was
worse on this sample.** Failure modes: four of six runs returned a `(counts, skipped)`
tuple instead of a dict with a `skipped` key; one raised `NameError: is_valid`; the one
pass (`events`, cold) returned `{"open": 1, "close": 1, "skipped": 2}`.

The fixture contract was tightened once (explicitly "a dict, not a tuple") and both arms
were re-run under the same wording, so the comparison is fair. The honest conclusion:
**the store is durable evidence, not a demonstrated capability gain.** A single
three-fixture sample cannot show learning either way; it does show the hint is not
free — it costs prompt budget in a lane that is already step-limited.

Evidence: `state/evidence/learning_experiment_20261102.json`.

---

## 4. REGRESSION

```text
186 passed in 8.95s
```

Fifteen suites, including four new author-lane cases: only-permitted-context handoff,
out-of-scope edit refused **and restored**, acceptance failure restored, and a commit
that contains exactly the task file.

---

## 5. STATE

* Task commits: `9e8e2cdb`, `e1585917` (plus `883a7fed` from the earlier campaign).
* No lock, no STOP, no worker, no resident model.
* Campaign serve stopped; operator daemon restored (`cpu`/`q4_0`, 0 resident, GPU 0 MiB).
* Campaign Ty profiles keep their explicit **f16** override; the operator's global
  `q4_0` remains untouched.

---

## 6. VERDICT

**READY**, scoped exactly to **DeepSeek-authored, Ty-supervised autonomous repair**:
three real defects fixed by the author, each gated by an independent probe that flipped
fail→pass, each committed task-only by the supervisor with scope audit and restore
discipline. This is not a claim about the broader NorthstarOS product, and the learning
claim is explicitly **not** proven.

---

## 7. NEXT DECISION (one)

Authorise the **backlog pass** (inspect the repository, freeze up to 5 further
contracts, work them in order under the same 8-task / 150-minute limits) — or stop here.

The backlog pass was **not run** in this turn: the qualification and the learning
measurement consumed the practical budget, and inventing contracts to keep the loop
alive would violate the directive. Everything needed to start it is in place.
