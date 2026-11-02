# Unit A + Unit B — simple-mode deliverable package and auth-test healing

**Campaign:** `ty-simple-mode-labeled` (Unit A) + `ty-auth-test-ordering` (Unit B)
**Date:** 2026-11-02
**Author:** DeepSeek V4.1 Flash (opencode-go, operator session); local supervisor `qwen3.5:4b`
**Branch:** `feature/chrome-connect-3.0` — base `533f164c`

---

## VERDICT

**PARTIALLY READY.** Both units are complete and verified against live machinery, but
the repository suite is not clean: 30 failures remain, all outside this campaign's
files, in four root causes named below. Nothing in this campaign is unimplemented or
unverified; "partially" describes the repo, not the units.

| Unit | Status | Evidence class |
|---|---|---|
| A — `ty-simple-mode-labeled` | **complete** | live render + scripted probe `t11` PASS |
| B — `ty-auth-test-ordering` | **complete** | 7 assertions corrected, 0 skips, 94 suite tests re-run |

---

## PER-UNIT BREAKDOWN

### Unit A — `ty-simple-mode-labeled`

**Objective.** An adherence-accepted render must become a complete, inspectable package
without a second manual step, and must be reopenable from the UI.

**Steps (8).**
1. `Northstar_backend/deliverables.py` — the package writer, gate and reader.
2. `GenerateIn.deliver` (schema field, default false) — hand-off is opt-in per request.
3. Hand-off wired into `POST /api/design-studio/generate`: render → `classify_form`
   (local `qwen3.5:4b`) → `adherence_verdict` → `write_deliverable`.
4. `GET /api/design-studio/deliverables` — manifests, newest first.
5. `GET /api/design-studio/deliverables/{run_id}/final` — the packaged PNG.
6. `northstar-os-ui/src/pages/internal/design-studio/Deliverables.jsx` + section entry
   in `DesignStudio.jsx`.
7. `.gitignore` — `state/deliverables/` is user output, not source.
8. `state/probes/t11_simple_mode_deliverable.py` — the scripted acceptance gate.

**Self-review catches (7).**
- An unreachable vision lane must not read as a pass → `adherence_verdict` returns
  `ok: false` with the reason.
- `manifest.files` was computed before `manifest.json` existed, so the manifest
  under-reported its own folder → fixed and asserted.
- Unknown fields are omitted, never nulled or filled with `TODO` → asserted by walking
  the manifest for nulls and scanning for placeholder words.
- `read_final` resolves and checks the root so a `run_id` cannot escape the folder.
- Runtime output is user data → gitignored.
- **A real outage found it:** run 1 of the probe failed with
  `reason: "vision lane unavailable"`, `observed: null`. The gate behaved correctly
  (no folder written) but the refusal dropped the underlying cause. `adherence_verdict`
  now carries `detail`, and a test pins it.
- Cause of that outage: Ollama had stopped (no process, no listener on 11434) between
  the 06:37 accepted run and the 06:52 probe. Recovered by starting the existing local
  binary — no download, no model pull.

**Commits.** `64a0f3af` (feature), `adb376d1` (diagnostics detail — this report's commit).

**Live proof — accepted run.**

```
run_id     3b0f8baf-2f66-4b0a-a836-1aefd2473b3f
folder     state/deliverables/3b0f8baf-2f66-4b0a-a836-1aefd2473b3f
files      adherence.json, brief.txt, citations.json, final.png, manifest.json
image      1024×1024 / 944,146 bytes
verdict    pouch -> pouch (ok=True, qwen3.5:4b)
elapsed    72.9 s end to end (probe, incl. render + vision)
```

**Live proof — refused run.** Requested `jar`, brief described a stand-up pouch; the
vision lane observed `bottle` → `ok: false`, `deliverable: null`, folders 1 → 1. The
render still exists as an asset (`14a29dce-…`); only the package is withheld.

**Read-back proof.** `GET …/deliverables/{run}/final` → 200, `image/png`, 1,448,787
bytes, PNG magic intact; unknown run → 404.

**Sample manifest (verbatim, `3b0f8baf-…/manifest.json`).**

```json
{
  "run_id": "3b0f8baf-2f66-4b0a-a836-1aefd2473b3f",
  "created_at": "2026-11-02T06:57:01",
  "brief": "a 6 oz stand-up pouch of organic lion's mane mushroom powder on a warm neutral background, soft studio light, premium packaging photography, no text, no lettering",
  "adherence": {
    "ok": true,
    "requested": "pouch",
    "observed": "pouch",
    "model": "qwen3.5:4b"
  },
  "files": [
    "adherence.json",
    "brief.txt",
    "citations.json",
    "final.png",
    "manifest.json"
  ],
  "bytes": 944146,
  "citations": [
    {
      "component": "studio_generation.generate_image",
      "kind": "local",
      "source": "repo:Northstar_backend/studio_generation.py",
      "license": "project code"
    },
    {
      "component": "comfyui workflow: flux3-image-klein-nvfp4",
      "kind": "local",
      "source": "repo:Northstar_backend/studio_generation.py (workflow builder)",
      "license": "FLUX.1 [dev] non-commercial (local bench)"
    }
  ],
  "image_size": [1024, 1024],
  "model": "flux3-image-klein-nvfp4",
  "tier": "draft",
  "seed": 821042013,
  "asset_id": "57e52356-fb10-4188-8234-41e5aaecc5be",
  "requested_form": "pouch"
}
```

Every field is a measured or submitted value. There is no `null`, no `TODO`, no
invented key; a field that cannot be resolved is absent.

**UI.** `npm run build` → 0 errors; the built bundle carries `deliverables-panel` and
the endpoint path. **No browser was run** — the UI check is static (bundle + endpoint
contract), and is reported as such rather than as a visual pass.

### Unit B — `ty-auth-test-ordering`

**Objective.** Eliminate the recurring `test_text_fidelity.py` failure and stop it
recurring in every report.

**Root cause.** Not auth ordering. `main.py` sets `app.state.dev_auto_session`, and the
dev-only loopback shim then mints the demo identity for any loopback request — the
behaviour sanctioned by the AGENTS.md *DEV-ONLY LOCALHOST EXCEPTION*. The tests asserted
401 for an anonymous loopback client, so the dependency resolved, the handler ran, and
the tests failed on the handler's own 404 / body-validation 422.

**The isolation that proved it.**

| Request | Result | Reading |
|---|---|---|
| no headers | 404 `Asset not found` | handler ran → dependency resolved |
| `Authorization: Bearer garbage` | 401 `Invalid session.` | dependency ran and rejected |
| `X-User-Id: demo-t2` | 404 | producer correct |

**Steps (4).** Reproduce → isolate (three-way header probe) → correct the assertion to
the hosted fail-closed path with `dev_auto_session` off and a `finally` restore →
extend the same correction to the four remaining anonymous-401 studio tests once the
full suite surfaced them.

**Self-review catches (3).** The failing status was the handler's, not the dependency's,
so "ordering" was the wrong hypothesis; the shim is sanctioned, so the test was wrong,
not the app; restore the app flag so later tests keep dev behaviour.

**Commits.** `7ee328fc`, `670792fb`, `199293d0`. No skip marks were added and no
assertion was deleted.

---

## REGRESSION SUITE

**Directly touched files.**

| Files | Result |
|---|---|
| `test_deliverables.py` | 10 passed |
| `test_text_fidelity.py` + `test_mockup_compositor.py` | 31 passed |
| `+ test_design_studio_lanes.py` | 40 passed |
| `test_design_studio_print.py` + `_re_ext.py` + `_scenes.py` | 23 passed |

**The reported auth issue is resolved, not documented-away.** The two failures that
appeared in every previous report (`test_text_check_endpoint_auth_and_404`,
`test_compose_endpoints`) pass, and three more of the same class were found and fixed.

**Full backend suite** (`python -m pytest -q`, 731.44 s):

```
34 failed, 5639 passed, 117 skipped, 2 xfailed, 88 subtests passed
```

4 of those 34 were the studio auth cases fixed after that run, leaving **30 failures,
all explained, none in this campaign's files**:

| Root cause | Count | Where |
|---|---|---|
| `autothink/backend/server.py:49` imports `build_system_prompt_with_context`, which `autothink/backend/llm_adapter.py` no longer exports | 11 | `test_autothink_routes` (8), `test_autothink_auth_boundary` (2), `test_ui_route_contract` live subtest (1) |
| `agent_kernel/local_model.py:89` — `NameError: num_ctx is not defined` | 5 | `test_local_model` |
| Dev-shim tests build a Starlette `Request` without `app` → `KeyError: 'app'` | 5 | `test_session_cookie_contract::DevShimSessionTests` |
| Stale fixtures/invariants in tests, unrelated to this campaign (route count 53 vs 57, HITL totals, shell-mode plan gates, two guard-prompt strings, a sample URL in `HitlQueue.jsx`) | 8 | `test_frontend_gate`, `test_autonomy_hitl_pathlike`, `test_hitl_counts`, `test_shell_modes` (2), `test_coding_guardrails`, `test_generation_guards`, `test_ui_route_contract` |
| Order-dependent: passes alone (24 passed), fails only inside the full run | 1 | `test_provider_suite` |

The first two rows are real code defects in the working tree — the top of the next
campaign, not this one.

---

## SPEND & RESIDUE

- **Cloud / Go spend this campaign: $0.00.** The author lane is this operator session;
  no `opencode run` invocations were made. Ledger `state/go_usage_ledger.jsonl` is
  unchanged at 11 entries, **$0.005656 cumulative** — 0.08 % of the $7.20 / 5 h halt
  share. Remaining ≈ **$7.1943** in the window (plus the untouched weekly/monthly shares).
- **Renders:** 4 live renders, all local on the operator GPU at **$0** (one accepted run
  later deleted during the `files` fix, one gate-refused run, two accepted runs kept).
- **Downloads:** none. No model pull, no package install.
- **Residue:** scratch `tmp-probe/` removed; `state/deliverables/` holds 2 accepted
  packages (user output, gitignored); no new daemons from this campaign. The backend on
  8000 is the operator's launcher, restarted 3× and still `armed: true`; Ollama was
  restarted at 06:56 because it had stopped, and is still running.

---

## DECISIONS & NEXT STEPS

**Decision anchors.**

1. **The gate is inline and writes nothing on refusal.** Verification is not a later
   audit step; a run that fails the vision check leaves the filesystem untouched
   (proved: folders 1 → 1) while the render survives as an asset.
2. **Unknown is absence, not null.** A manifest field that cannot be measured is
   omitted. Enforced by a probe that walks for nulls and scans for placeholder words —
   this is the rule that stops "honest" manifests decaying into `TODO`.
3. **A test that contradicts a sanctioned environment feature is corrected on the
   surface that owns the behaviour, never skipped.** Corollary recorded: the dev shim
   now contradicts `test_session_cookie_contract`'s "no header is refused even in
   development", and that conflict is left visible rather than papered over.
4. **A package must describe itself.** `manifest.files` includes `manifest.json`; a
   listing that omits the file doing the listing is a small lie that compounds.

**Next campaign — one operator choice.**

| Option | What it buys |
|---|---|
| **A. Suite green** (recommended) | Fix the `autothink` import break (11 failures) and `local_model` `num_ctx` (5). Takes the suite from 30 unexplained-by-omission failures to a defensible baseline. |
| B. Creative quality | Label/mockup composition on top of the delivered render — the package design, not just the packaging form. |
| C. Thematic expansion | New categories and templates on the now-stable pipeline. |
| D. Settle the dev-shim contract | Decide the security contract between the sanctioned demo session and `test_session_cookie_contract` (5 tests). |

Option A is recommended because the two defects it fixes make the local lane
(`local_model`) and the autothink route family unusable as test surfaces, which
undercuts every later measurement.
