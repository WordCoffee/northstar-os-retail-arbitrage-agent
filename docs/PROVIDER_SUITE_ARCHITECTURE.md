# Provider Tool Suite — local bench vs cloud customer lane

**Status:** shipped 2026-10-21 · `feature/v4.1-mesh`
**Code:** `shared/provider-suite.json` (data) · `Northstar_backend/provider_suite.py` (resolver)
**API:** `GET /api/v1/provider-suite[?provider=local|cloud]` · **UI:** Master Brain → *Provider tool suite*

---

## 1. The problem this solves

`shared/model-suite.json` already answers *"which model for tier T2?"*. It did not
answer the more important question: **which tools may the brain touch at all on
this lane?**

The distinction is licensing, not preference:

| | LOCAL bench | CLOUD customer lane |
|---|---|---|
| Who sees the output | the operator | paying customers |
| Non-commercial weights | **allowed** (`FLUX.1 [dev]`, unverified LoRA weights) | **blocked** |
| Copyleft agent runtimes | allowed (AGPL/GPL as a separate process) | needs review |
| Cost | free, local GPU | metered per call |
| Arming | `MEDIA_GEN_LIVE` for media | per-provider key + live flag |

Running `flux1-dev` on the operator's bench for internal concepts is fine. Shipping
its output to a customer is a licence violation. Before this module there was no
enforcement point — only prose in the constitution.

A second, subtler trap: **"local lane" does not mean "offline"**. OpenMontage is a
local install that still reaches out to Archive.org and (optionally) 60+ paid APIs.
So the suite records `network` per tool instead of pretending a lane is a network
boundary.

---

## 2. The two axes (do not conflate them)

Every tool resolves on two independent axes:

1. **allowed** — lane membership **and** licence permit it here.
2. **installed** — it is actually present on this machine.

`usable = allowed AND installed AND gate armed`.

That is why UltraTex reports *allowed but not installed* today: the licence question
and the disk question are different questions. Collapsing them would let a stale
JSON flag claim a capability that does not exist.

```bash
python Northstar_backend/provider_suite.py
python Northstar_backend/provider_suite.py --provider cloud --json
python Northstar_backend/provider_suite.py --check ultratex --provider cloud
```

### Reason codes (stable strings)

| Code | Meaning |
|---|---|
| `ok` | usable now |
| `not_in_lane` | declared for a different lane |
| `license_noncommercial` | licence forbids commercial output |
| `weights_license_unverified` | model weights carry no stated commercial grant |
| `gate_not_armed` | present, but the live gate is off |
| `not_installed` | allowed, not on disk |
| `agpl_network_copyleft_unreviewed` | AGPL §13 network clause, legal question open |
| `unknown_tool` / `unknown_provider` | fail closed |

Licence is evaluated **before** lane membership on purpose: if a non-commercial
tool is ever mis-listed on the cloud lane, the licence still blocks it and the
reason says why.

---

## 3. What was researched, and what it means here

### UltraTex — local 3D texturing (the one that fits best)

`visualbruno/ComfyUI-UltraTex` · SIGGRAPH Asia 2026 · `MIT` node code

Untextured mesh + one reference image → six 2048² texture views → baked UV texture,
exported as GLB. Nodes: Load LoRA, Foreground VAE Decoder, Prep (mesh + reference),
Sampler, Bake Texture.

- **Licence split:** node code MIT; base `FLUX.2-Klein-base-9B` is Apache-2.0;
  **the UltraTex LoRA weights from ModelScope state no commercial grant** →
  `weights_license_unverified` → local lane only until confirmed in writing.
- **Hardware:** measured on an RTX 3080 Laptop 16 GB, fp8 — ~2.3 min per workflow at
  1024, ~9.6 min at 2048. Same class as this box.
- **Prerequisite already satisfied:** it needs Triton on Windows; `triton-windows
  3.8.0.post29` is already installed (it fixed KJNodes' PatchTritonVAE, 00_STATE).
- **Why it matters:** Product Designer already has meshes. Today mockups are flat
  plates. UltraTex turns a mesh + the approved hero plate into a textured 3D prop,
  which then feeds local video (Wan 2.2) or the Blender lane. Zero marginal cost.

### OpenMontage — agentic video harness

`calesthio/OpenMontage` · `AGPL-3.0` · GitHub repo of the day

10+ pipelines (animated explainer, cinematic, talking head, documentary montage,
clip factory, localization, podcast repurpose, screen demo), 100+ tools, 60+ provider
integrations, 700+ agent-skill markdown files. Structured flow:
`research → proposal → script → scene_plan → assets → edit → compose`, with a stage
director skill per stage and a human approval gate at creative decisions.

The zero-key path is the interesting part: **Piper TTS + Remotion/HyperFrames +
FFmpeg + Archive.org / NASA / Wikimedia footage**. Published example costs: $1.33
for a 60s short with cloud models, ~$4–5 for multi-world showcases.

- **Two separate facts, both true:**
  1. AGPL-3.0 **does** permit commercial use, but §13's network clause is a legal
     question we have not answered → `cloud_block` → local lane by default.
  2. It is a *harness*, not a model. "Local lane" means *installed on this machine*,
     not *no network*.
- **Verdict: clone the pattern, not the code.** Its pipeline/stage-skill structure is
  the most reusable idea in the repo and carries no licence obligation. Vendoring the
  AGPL tree into Northstar would put the whole app under review for a feature we can
  reimplement in a fraction of the size.

### Agent harnesses (the category)

A harness is the runtime layer around a model — tools, skills, sessions, approvals.
Northstar already has one: this repo's constitution + `model_router.py` +
Chrome Connect + the room structure. The 2026 trend is that harness quality, not
model choice, determines what an agent can actually finish. `provider-suite.json`
is the missing manifest that tells the harness what it is allowed to pick up.

---

## 4. The three adoptions, ranked by value per unit of risk

| # | Adoption | Lane | Cost | Blocker | Verdict |
|---|---|---|---|---|---|
| 1 | **UltraTex** ComfyUI pack → textured 3D product props | local | $0 | LoRA weights licence (needs written confirmation or an Apache-2.0 substitute) | Ready to install; install once licence is confirmed or accept bench-only use |
| 2 | **OpenMontage stage-skill pattern** → our own pipeline directors for Design Studio / ListingForge / SocialPulse | both | $0 | none (pattern, not code) | Do now |
| 3 | **OpenMontage as an external local tool** (`OPENMONTAGE_ROOT`, invoked headless, output consumed as a file) | local only | $0 free path | AGPL §13 review before any customer-facing use | Deferred until a real video order exists |

Explicitly **not** done: nothing auto-installed, no repo vendored, no AGPL code in
a cloud path, no new spend, no provider key touched.

---

## 5. How to add a tool

Add one entry to `shared/provider-suite.json`:

```json
"my_tool": {
  "name": "Human name", "kind": "image|edit|video|three_d|voice|stt|ocr|browser|harness|engine",
  "runtime": "comfyui|python|node|cli|api",
  "lanes": ["local"],
  "license": "SPDX-or-explicit",
  "weights_license": "unverified",        // optional; blocks cloud when unverified
  "commercial_ok": false,
  "network": false,
  "cost": "free_local",
  "installed": "installed|ready|absent",
  "gate": "MEDIA_GEN_LIVE",               // optional env gate
  "gate_mode": "armed|present",           // armed = must equal "1"; present = non-empty
  "unlocks": "one line the brain can read",
  "notes": "honest caveat — the thing a sales page would leave out"
}
```

Rules:
- **Never** put a credential value in this file — key *names* only, and only in notes.
- `installed` is a declaration, not a probe. Callers may pass `confirmed=[...]` with
  ids they just proved present (same pattern as `model_router.catalog(installed_local)`).
- A tool with an unclear licence gets `commercial_ok: false`. Unknown is not "probably fine".

---

## 6. Verification

```
python -m pytest test_provider_suite.py -q     # 23 passed
npm run build                                  # 0 errors
```

Covered: both lanes load · every declared tool resolves on its own lane · local
allows non-commercial weights · cloud blocks them with the right code · AGPL harness
blocked on cloud and allowed locally · cloud-only tool refused locally · unknown tool
and unknown provider fail closed · install and gate are separate axes · gate
`armed` vs `present` · active-lane env override · catalog never leaks credential
values · endpoint envelope.
