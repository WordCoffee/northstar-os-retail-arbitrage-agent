# D16 — Model Scout lane

**Status:** harness built, eval sets fixed, leaderboard written. **No GPU measurement yet** —
the single GPU belongs to the Director's lane, so this unit ships the measurement command
and refuses to fake its output. Every role's recommendation currently reads `unmeasured`.

Files:

| file | what it is |
|---|---|
| `tools/model_scout.py` | runner, scorers, swap rule, quarantine + restore plans |
| `tools/model_scout/evals/router_18.json` | 18-item intent → lane eval (fixed) |
| `tools/model_scout/evals/json_adherence_10.json` | 10-item strict-JSON eval (fixed) |
| `ty/model_roles.json` | per-role incumbents, budgets, candidates, evidence sources |
| `ty/model_leaderboard.json` | tracked leaderboard (mirrors to `state/intel/models.json`) |
| `Northstar_backend/test_model_scout.py` | 37 tests, no network, no Ollama |

---

## 1. The 6/18 baseline is not an 18-item router set

The work order says Bojo measured **6/18** on its routing eval. On disk:

`reports/ty/model_bench_bojo_gpu_20261107.json` is **3 manager tasks** (`MGR-1`…`MGR-3`),
each scored 0–2 on three checks (`asks`, `no_fabrication`, `routes`): 3 × 6 = **18 points**,
score **6**. That is a manager-behaviour score from `tools/model_bench.py`, not eighteen
routing questions.

Consequence, recorded in `ty/model_roles.json` → `baseline_reconciliation` and repeated in the
leaderboard: **6/18 is kept as history but is not comparable** to the new 18-item router set.
The first Director `--run` measures `bojo:latest` on the same 18 items as the candidates, and
the swap rule applies only to measurements from the same eval set and item count.

## 2. Roles and incumbents (read from the repo)

| role | lane | incumbent | budget | source |
|---|---|---|---|---|
| bojo-router | bojo | `bojo:latest` | 3.5 GB | `tools/gpu_budget.py` `ROLE_MODELS`, `state/director/caps.json` |
| planner-coder | coder | `qwen3:8b` | 7.0 GB | `ROLE_MODELS`, caps measured 6.63 GB |
| vision | vision | `llava:7b` | 8.0 GB | D7 decision; `qwen2.5vl:7b` quarantined pending retest |
| gui-grounding | gui_grounding | **none** | 8.0 GB | no model registered; UI Automation is the deterministic primary |
| embeddings | embeddings | `qwen3-embedding:0.6b` | 2.5 GB | `ROLE_MODELS` |
| image | image | ComfyUI workflows (FLUX) | 11.0 GB | not an Ollama tag; never measured with `/api/chat` |

Budget conflict, resolved explicitly: `caps.json` says vision 6.5 GB, `tools/gpu_budget.py`
(the manager that enforces it) says 8.0 GB. **8.0 is used.**

## 3. Eval sets

`router_18.json` — 18 cases, six lanes, three cases each:
`bojo`, `coder`, `vision`, `gui_grounding`, `embeddings`, `image`.
Scoring: exactly one lane parsed from the reply; correct when it equals `expect`.
`{"lane": ...}` wins over prose; word-boundary aliases are the only leniency.
sha256 `79afc1a1…51904`.

`json_adherence_10.json` — 10 strict-JSON cases with declarative schemas
(`type`, `enum`, `required`, `additionalProperties: false`, `min/max`, `items`).
A reply is correct only when it is **strict** JSON (a single ``` fence is allowed) **and**
validates. Prose around a valid object fails, which is the point.
sha256 `07877cfc…f3647`.

Candidates (all already installed — the scout never pulls):
`qwen3.5:4b` (first, per the work order), `qwen3.5:2b`, `gemma3:4b`, `qwen2.5-coder:3b`.

## 4. Swap rule (implemented, tested, never automatic)

A candidate may replace an incumbent only when **both** hold:

1. `candidate_correct - incumbent_correct >= 2` on the **same** eval set and item count;
2. it fits the role: measured VRAM ≤ the role budget **and** free RAM ≥ 2.0 GB.

Anything else returns `keep-incumbent` with the reason (`margin +1 < required +2`,
`beats the margin but does not fit: 4.2 GB VRAM > 3.5 GB role budget`, …).
`decide()` is a pure function; `recommend()` picks at most one replacement per role.
`swap_rule.auto_swap` is `false` in the leaderboard.

## 5. The GPU command the Director runs

```powershell
python tools/model_scout.py --run --role bojo-router --models qwen3.5:4b,qwen3.5:2b,gemma3:4b,qwen2.5-coder:3b
```

The incumbent (`bojo:latest`) is added automatically unless `--no-incumbent` is passed, so the
margin is computed against a measurement from the same run. Expected shape:

- takes `tools/gpu_budget.py`'s lock (`model_scout:bojo-router`), refuses if another lane holds it;
- `enforce(keep=[])` first, then load → measure → `unload` + `wait_until_unloaded()` between models;
- records per model: `correct/items`, per-item rows, mean and p95 latency, `size_vram_gb`,
  `processor`, free RAM; a model that is not installed is recorded `not_installed` and skipped;
- writes `ty/model_leaderboard.json` and the `state/intel/models.json` mirror;
- writes a recommendation, never a swap.

`OLLAMA_MAX_LOADED_MODELS=1` is a **server-process** setting. The runner cannot change a running
server, so it records what the environment actually says and enforces the same rule itself by
keeping one model resident at a time. It does not claim a pin it did not set.

`python tools/model_scout.py --help` (real output):

```
usage: model_scout [-h] [--run] [--role ROLE] [--models MODELS]
                   [--no-incumbent] [--plan] [--restore ROLE] [--apply]
                   [--out OUT] [--no-mirror] [--num-predict NUM_PREDICT]
                   [--timeout TIMEOUT] [--lock-ttl-s LOCK_TTL_S]
                   [--list-evals]

D16 model scout: fixed evals, measured candidates, a written recommendation.

options:
  -h, --help            show this help message and exit
  --run                 measure models on the GPU (one resident at a time)
  --role ROLE           role to scout (see ty/model_roles.json)
  --models MODELS       comma-separated candidate tags, already installed
  --no-incumbent        do not add the role incumbent to the model list
  --plan                write the leaderboard skeleton; no GPU
  --restore ROLE        print (and with --apply run) the restore plan
  --apply               with --restore: run the plan
  --out OUT             leaderboard path
  --no-mirror           do not write state/intel/models.json
  --num-predict NUM_PREDICT
  --timeout TIMEOUT
  --lock-ttl-s LOCK_TTL_S
  --list-evals          show eval sets without running anything
```

Planner/coder scouting is the same command with `--role planner-coder`; its eval is
`json_adherence` only — there is **no coding eval in this unit**, and no coding claim is made.

## 6. Quarantine and restore contract

- **Quarantine is a copy, never a move.** On a `replace` recommendation the leaderboard records
  `ollama cp <incumbent> <base>:quarantine-YYYYMMDD-HHMMSS`; the original tag stays resolvable
  and nothing is deleted (`delete_original: false`).
- **Restore** is generated from the leaderboard, not from memory:

```powershell
python tools/model_scout.py --restore bojo-router            # plan only (dry run)
python tools/model_scout.py --restore bojo-router --apply    # runs exactly the printed commands
```

The plan prints the `ollama cp` (only when a quarantine tag exists), an `ollama show` verification,
and the exact `ROLE_MODELS[...]` repoint for `tools/gpu_budget.py`. Tests assert the commands,
the `bojo:quarantine-20261108-000000` tag shape, and that an unknown role raises.
The plan generation is tested; **no real model move was performed**.

## 7. Evidence

```
$ python -m pytest Northstar_backend/test_model_scout.py -q
37 passed in 0.17s
```

Covered: eval parsing (counts, unique ids, lane vocabulary, schema presence, declared-count
mismatch), lane parsing (JSON wins, word boundaries, aliases), router maths (18/18, 6/18
reproduction), strict-JSON detection (fence ok, prose fails), schema validation (extra key,
enum, min/max, required, nested), swap rule (margin 2, margin 1, over budget, RAM floor,
unmeasured incumbent), budget-constant parity with `tools/gpu_budget.py`, leaderboard build +
write + mirror, replacement/quarantine, not-installed candidate, restore plan, CLI surface.

`python tools/model_scout.py --plan` writes the tracked leaderboard and the intel mirror;
`--list-evals` prints both sets and their item counts.
