# Unattended autonomy over the OpenCode Go author lane (2026-11-02)

The operator ferry is gone: the supervisor now calls the model itself through the
**existing OpenCode Go subscription** (`opencode run`), with accounting, a quota gate
and the same verification. One task ran end to end unattended and was committed.

**No OpenRouter call was made.** The OpenRouter key remains present and unused.

---

## 1. LANE

| | |
|---|---|
| Transport | `opencode run --model opencode-go/deepseek-v4.1-flash --format json` (CLI on the subscription) |
| Model id | **`opencode-go/deepseek-v4.1-flash`** — resolved from the harness catalogue, not guessed |
| Pricing (from the catalogue) | $0.15 / M input, $0.60 / M output, $0.003 / M cache read |
| Key handling | the local config defines `ollama`, `openrouter`, `llamacpp` only — **no `opencode-go` base URL or key exists**; the lane uses the harness's own auth, so **no key is read, passed, logged or printed**. Tests assert no key material in prompts or ledger |
| Session routing | one `--title ty-<task>` per task; the CLI returns a stable session id |
| Tool calling | the model returns **one JSON object** (path / search / replace); the lane validates and applies it, so a plain-text reply is never treated as a tool call |

Probe evidence (`state/go_usage_ledger.jsonl`):

```text
probe:go-lane-interface   9,663 in / 8 out / 512 cache read   $0.001456   cli
probe:go-lane-edit-shape  (reply was malformed JSON)          $0.002000   estimate
```

**Usage fields exist**: `step_finish` carries `cost` and `tokens{input, output,
reasoning, cache{read, write}}`. They are **not always present** — the task run returned
no usage block, so the lane now falls back to a conservative estimate from payload
length (tested).

**Overage balance:** no programmatic usage endpoint exists; none was queried. Limits
recorded at implementation time: **$12 / 5 h, $30 / week, $60 / month**.

---

## 2. ACCOUNTING

`state/go_usage_ledger.jsonl` (append-only) records task, model, tokens, cost, source
(`cli` or `estimate`) and epoch. Windows are summed per request:

```text
5h: $0.0035/$7.20 halt | week: $0.0035/$15.00 halt | month: $0.0035/$30.00 halt
```

Halt shares: **60% of 5 h, 50% of week, 50% of month**; `preflight` refuses to open a
task that would cross any of them. A CLI quota/429 is caught as a `quota` result, the
task stays incomplete and the campaign stops — **no retry blast**. Both paths are unit
tested (13 tests: arithmetic, rollover, estimate-vs-actual, quota halt, no-leak).

---

## 3. DECISIONS MADE (autonomous, evidence-based)

1. **Transport:** rejected an API-client build for Go after finding no `opencode-go`
   endpoint or credential in the local config; used the CLI on the existing
   subscription instead. Evidence: `opencode.json` providers = ollama, openrouter,
   llamacpp.
2. **Billing:** never touched the OpenRouter key — `deepseek-v4.1-flash:floor` is
   per-token billing and this run is not authorised for it.
3. **Edit shape:** rejected full-file rewrites (a lane cannot reproduce a 16 KB module)
   in favour of one exact search/replace validated against the contract's write scope.
4. **First target:** `print_prep.face_pixels` accepted a **collinear quad** as a
   5.0 × 10.0 face; chosen because it is geometry, has an objective check, and sits
   next to the print gate that was just repaired.
5. **Rejected:** `cost_model.ppc_fee/refund` boundary bugs — billing logic, excluded.

---

## 4. TASKS

| Task | Class | Probe | Commit | Trajectory |
|---|---|---|---|---|
| `ty-quad-area-guard` | geometry-degenerate-quad | `t8` FAIL(1) → **PASS** | **`c0111fde`** (+13, one file) | `geometry-degenerate-quad.jsonl` |

The model's first six replies were rejected by the lane's JSON contract; the seventh
applied cleanly (recorded as `envelope_rejections: 6`). The supervisor then ran the
probe, the scope audit and the task-only commit. Seven accepted repairs this session.

**One limit observed and fixed:** the 16 KB contract file exceeded the Windows
command-line limit, so the prompt now goes over **stdin** (the CLI reads it when no
message argument is given).

---

## 5. REGRESSION

```text
253 passed, 1 skipped in 12.15s
```

Twenty-one suites, including the new `test_go_author.py` (13 cases) and
`test_author_lane.py` (4).

---

## 6. STATE

* HEAD before this report: `c0111fde` (task) — lane code committed after.
* No lock, no STOP, no worker, no resident model; no Ollama/Bojo change.
* Learning store: **7 trajectories**; threshold for the next measurement is 10, not
  reached, so the negative cold-vs-informed delta stands.

---

## 7. VERDICT

**READY — UNATTENDED**, scoped to *supervised, DeepSeek-authored repair dispatched
through the OpenCode Go subscription*: the ferry is removed, one task ran and committed
without operator involvement, accounting and the quota gate are in place and tested.

**QUOTA-BOUNDED:** the conservative halt shares are enforced before every task; a
server-side 429 stops the campaign cleanly.

**Not exercised:** a multi-task campaign (max 20 tasks / 8 h) — one task was run, so
the loop's endurance is untested.

---

## 8. NEXT DECISION (one)

Authorise a **multi-task unattended campaign** (up to 20 tasks, 8 h, the quota gate
live) — or stop at the single-task proof.

Launch is `scripts\ty_go_autonomy.cmd`; monitor with `--status`, stop with `--stop`.
