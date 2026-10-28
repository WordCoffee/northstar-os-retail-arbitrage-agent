# 1.6 — SIMPLE MODE UI (SMUI)
## Phase 2 research deliverable — REA program

**Date:** 2026-10-28
**Scope:** measure what operators actually ask simple mode for, find where the
intent dies between the turn and the tool, and specify the interaction changes
that are justified by those numbers.
**Method:** corpus mining (`chat_messages` / `chat_runs` / `chat_tool_calls` in
`Northstar_backend/data/northstar.db`), code read, and WCAG contrast arithmetic.
**Spend:** 0. **Amazon contact:** 0.

Instrument: `tools/rea_smui_intents.py` → `reports/rea_probe/smui_intents.json`
(aggregate counts only; no message text is retained).

---

## 1. The corpus (real numbers, with the sample size stated)

| Measure | Value |
|---|---|
| chat sessions | **26** |
| chat messages | **121** |
| user turns scanned | **60** |
| chat runs | **58** |
| tool calls recorded | **39** |
| messages per session | **4.65** |
| **tool calls per session** | **1.50** |

**Read that last row honestly:** a session averages ~4.7 messages and 1.5 tool
calls. Simple mode is not being used as a multi-step workshop — it is being used
for one or two exchanges and then abandoned or completed elsewhere. That is
either efficiency or leakage; §2 separates the two.

Caveat that belongs in the same breath: **60 user turns is a thin sample.** It is
enough to see a ratio this lopsided, not enough to call it a trend.

---

## 2. Intent distribution and the gap that matters

Keyword classification over user turns (a turn can match more than one rule):

| Intent | Turns | The tool that should serve it | Calls recorded | Ratio |
|---|---|---|---|---|
| image render | **33** | `generate_image` | **15** | 0.45 |
| **label / pouch composite** | **21** | **`apply_label`** | **3** | **0.14** |
| A+ / listing content | 7 | (no dedicated tool) | — | — |
| logo / brand mark | 5 | (no dedicated tool) | — | — |
| status / help | 2 | `system_status` | 6 | 3.0 |

Full tool usage: `generate_image` 15, `creative_plan` 8, `system_status` 6,
`list_templates` 3, `apply_label` 3, `create_dieline` 2, `service_catalog` 1,
`knowledge_lookup` 1.

**Finding 1 — the label intent does not reach the label tool.** 21 turns mention
a label/pouch/bag; `apply_label` was called 3 times. The 2026-10-23 repair added
the tool and told the model in the system prompt that `apply_label` *is* the
structured-layer path — and the ratio is still 0.14. Something upstream is still
absorbing the request (most likely the model answering with a render +
explanation instead of chaining into the label pass).

**Finding 2 — a third of the work has no tool at all.** 12 of 60 turns
(A+ 7 + logo 5) ask for something no tool serves. That is the largest
*structural* hole in the surface, and it is the same hole the 1.2 and 1.4
research plans pointed at.

**Finding 3 — `system_status` is called more often than there are status
turns (6 vs 2).** Status is being checked *inside* other work (pre-flight around
renders), not as a user intent. Useful signal: status belongs in the background,
not as a user-facing control.

---

## 3. Code-level inventory

| Property | Measured |
|---|---|
| `ChatSurface.jsx` length | **1,831 lines** |
| `useState` hooks | **44** |
| `<Icon>` uses | **34** |
| `<select>` elements | **5** |
| `aria-live` regions | **1** (`role="log" aria-live="polite" aria-busy={streaming}`, line 1249) |
| keyboard handlers | 4 |
| column width | `--simple-col: clamp(760px, 78vw, 1360px)` (`simple.css:40`) |
| prose measure | `78ch` (`simple.css:41`) |

44 state variables in one component is the mechanical reason the interaction
model is hard to change: every new behaviour competes for the same render tree.

---

## 4. Journey maps (measured where possible)

### J1 — "put the label on the bag" (21 turns, 3 calls)
```
operator turn
  → render (generate_image)               ← consumes the turn
  → model explains the text limit
  → operator re-asks
  → (sometimes) apply_label
```
Observed: 3 of 21. The missing link is not the tool, it is the **automatic
chaining** after a render whose brief mentions a label.

### J2 — "make me a plate" (33 turns, 15 calls)
```
operator turn → generate_image → asset card → operator reacts
```
The healthiest path in the corpus: 1 turn ≈ 0.5 calls, and the 2026-10-23 fixes
(asset names, sizing report, voice) all live here.

### J3 — "write / improve the listing" (7 turns, 0 calls)
```
operator turn → prose answer → dead end
```
No tool, no artefact, no asset. The operator gets advice, not a deliverable.

---

## 5. Auto-chain proposal (what "one turn to a deliverable" actually requires)

| Trigger | Chain | Why |
|---|---|---|
| brief mentions label/pouch/bag **and** a render completed with no text | `apply_label` immediately, then OCR gate, then register | closes Finding 1 without a new intent parser |
| brief mentions A+/listing **and** a product/plate exists | build the arc (§1.2), return a module pack | closes Finding 2 |
| brief mentions logo **and** an attachment exists | crop/normalise → propose placements → ask once | logo work is 5 turns and zero tools today |
| any render | always report fitted size + engine max (already shipped) | keep the one healthy path healthy |

Rule: a chain may only auto-advance when **every** parameter it needs is already
present in the turn. If one is missing, ask exactly one question — never a form.

---

## 6. Progressive disclosure: what to measure, not assert

The composer was collapsed from six dropdowns into one row on 2026-10-23. Five
`<select>` elements remain behind the Options disclosure. **Which of them change
the output has not been measured** — and the plan's rule was "no opinion without
a diff". So this report does not recommend deleting any control; it specifies the
instrument:

For each of the 5 controls: hold the prompt fixed, change only that control,
render twice, compare (a) the request body sent to the engine, (b) the resulting
asset hash. A control whose change produces **no** request-body difference is
noise in the UI. This is a 5×2 render budget on the local lane, no spend.

`UNVERIFIED`: the control→output mapping (deliberately not guessed).

---

## 7. Accessibility (WCAG 2.2 AA), measured

Contrast computed against the simple-mode dark surface `#1a2435`:

| Token | Hex | Contrast | Verdict |
|---|---|---|---|
| `--ink` | `#f7f3ec` | **14.09 : 1** | pass (AAA) |
| `--ink-mid` | `#d2ccbf` | **9.74 : 1** | pass (AAA) |
| `--ink-soft` | `#a8a196` | **6.09 : 1** | pass (AA normal text) |
| **`--ink-faint`** | `#8d867a` | **4.32 : 1** | **fails 4.5 : 1 for normal text** (passes 3 : 1 for large text / UI components) |

That is a real, one-token defect: any body-size text using `--ink-faint` is below
AA. Fix is a 10 % lift on the token, not a redesign.

Structural status:

| Item | State | Gap |
|---|---|---|
| streaming transcript announced | one `role="log" aria-live="polite"` region | `aria-busy` toggles, but there is no `aria-relevant`/throttling policy — verbose streams can flood a screen reader |
| focus after send | 4 keyboard handlers | focus return to the composer is not asserted by a test |
| live streaming text | polite live region | acceptable; **assertive** would interrupt |
| keyboard reachability of artefact cards | 34 `<Icon>` controls | icon-only buttons need an accessible name each — spot-check, not exhaustively verified |
| reduced motion | plan graph / Ken-Burns style motion | no `prefers-reduced-motion` handling observed in `simple.css` |
| target size (2.5.8, AA in 2.2) | 14.5 px UI type, padded buttons | not measured |

---

## 8. BUILD CANDIDATES

| id | component | change | evidence (report §) | effort | risk | gate |
|---|---|---|---|---|---|---|
| U1 | `chat_router` turn directive | auto-chain `apply_label` when a label brief produced a render | §2 Finding 1: 21 turns → 3 calls | 3 h | medium; must not double-compose | none |
| U2 | `chat_tools` | add listing/A+ tool that returns the arc pack (depends on A1) | §2 Finding 2: 12/60 turns unserved | 6 h | medium | none |
| U3 | `chat_tools` | add logo placement tool | §2 Finding 2 | 4 h | medium | none |
| U4 | `simple.css` | lift `--ink-faint` to ≥ 4.5 : 1 | §7: 4.32 : 1 | 10 min | none | none |
| U5 | `ChatSurface.jsx` | split into composer / stream / artefacts (44 `useState` is the ceiling) | §3 | 1–2 d | high; refactor of a shipped surface | none |
| U6 | test | control-diff instrument for the 5 selects (§6) | §6 | 2 h | low; needs 10 local renders | none |
| U7 | `simple.css` | honour `prefers-reduced-motion` | §7 | 30 min | none | none |
| U8 | `chat_router` | throttle `aria-live` announcements (batch tokens) | §7 | 1 h | low | none |

**Rejected:** removing any composer control before U6 produces the diff; adding a
form-style parameter panel (the corpus shows 4.65 messages per session — a form
would make that worse, not better).

## 9. UNVERIFIED

- Intent counts are keyword matches, not classified intents; 60 user turns is a
  thin sample.
- Which composer controls change output (§6 instrument not yet run).
- Whether the 1.5 tool calls/session is efficiency or abandonment — that needs a
  completion signal (asset produced vs turn ended with prose), which the schema
  does not record today.
- Screen-reader behaviour of the live region was not tested with an actual
  screen reader.
- Target-size (WCAG 2.5.8) not measured.
