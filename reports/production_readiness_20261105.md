# Production readiness sweep — 2026-11-05

Mandate: scan and improve the whole Northstar OS service until the UI is
production-ready in quality and experience. Ad-hoc greps do not scale and do not
repeat, so the durable deliverable is a **scanner** — checks that either find
something or do not — plus the fixes it produced.

## The scanner

`tools/production_readiness_scan.py`, 16 tests
(`Northstar_backend/test_production_readiness_scan.py`), consumed by
`tools/improvement_backlog.py --scan` so a finding lands where work is queued.

| check | what it means | default |
|---|---|---|
| `dead-module` | a `src/lib` module nothing imports | yes |
| `button-no-type` | a button **inside a `<form>`** with no `type=` (it submits) | yes |
| `input-unlabelled` | `<input>/<select>/<textarea>` with no label and no `aria-label` | yes |
| `img-no-alt` | `<img>` with no `alt` | yes |
| `catch-swallowed` | an empty catch block | yes |
| `placeholder-copy` | TODO/FIXME/coming soon/lorem in shipped source | yes |
| `silent-except` | `except Exception: pass` in a non-test backend module | **opt-in** |

Two design decisions worth naming:

- **`silent-except` is opt-in.** 52 broad handlers exist and most are deliberate
  resilience (poll a transient API, unload a model best-effort, kill a process).
  Flagging all of them by default is how a scanner teaches people to ignore it.
- **Waivers are declared in the file**, as
  `readiness-scan: <check> waived - <reason>`, and printed in the report. Some
  findings are structurally undecidable to a static scan (a shared input has no
  label because its consumer supplies one); a visible, reviewable waiver beats
  permanent noise.

## The scanner had to be fixed before its findings could be trusted

The first run reported **95 findings and most were wrong**. Each of these was a
real defect in the scanner, found by reading the hits:

| false positive | cause | fix |
|---|---|---|
| 2 × `<img>` no alt | both were inside comments | strip comments before matching tags |
| 7 × input unlabelled | checkbox labelled by a following `<label htmlFor>` | resolve `id`/`htmlFor` pairs anywhere in the file |
| 2 × placeholder copy | the literal status string `'todo'` ("done" vs "todo") | make TODO/FIXME case-sensitive |
| 388 × button no type | a button outside a form cannot submit | scope the check to `<form>` |
| 52 × silent except | deliberate resilience | opt-in triage list |

The comment stripper also had a real bug worth recording: the first version
tracked string literals to decide what a `//` meant, and an apostrophe in JSX text
("don't") flipped its state so the rest of the file stopped being recognised as
code. It now uses a colon guard (`http://` survives, everything else after `//`
is a comment) and does not guess.

**Result: 95 findings → 1.**

## Fixes shipped

| commit | scope | result |
|---|---|---|
| `e74f5520` | the scanner + its 16 tests + `--scan` on the backlog tool | the tool exists and is consumed |
| `caa3c2fb` | command palette, shell command menu, pinned drawer, Packify brief, 2 passthrough libs | 12 findings closed |
| `3766d07d` | 9 admin/studio pages, 21 controls | `input-unlabelled` **0** |
| `c0bdf34a` | scanner precision | 95 → 1 finding |

Accessibility specifically: the two most-used navigation surfaces in the app —
the ⌘K palette and the shell command menu — announced an **unnamed text box** to a
screen reader. Both now have an accessible name, as do the pin-note field, the
Package Design brief field, the beta-ops filters, the invite form, the admin note,
the tester ticket form, the org-change reason fields, the memory search, the
spreadsheet editor, the Amazon-file edit cells and the search-term filters.

Placeholders were deliberately not treated as names; a colour swatch and a metric
cell get an interpolated name (`Palette colour 1`, `impressions`) so each is
distinguishable.

## The one finding left

`northstar-os-ui/src/lib/serviceGate.js` — a service-entitlement gate with **no
importer and no test**. Its own header says the decision "is enforced
server-side, not here". It is not dead by accident: `api.entitlements()` exists
and `serviceRegistry.js` already derives `studio.<id>` keys, so it could be wired
into a service surface — but that is a product decision (which surface, what a
denied service looks like), not a scan fix. Filed as `needs-author` rather than
deleted or wired blind.

## What this does not prove

- The scan is **static**. It cannot see a control that is labelled at runtime, or
  a layout that is unusable at 320 px, or a focus trap that does not return focus.
- No contrast, keyboard-traversal or screen-reader pass was run. `npm run
  test:contrast` exists and passes, but it checks tokens, not rendered pages.
- `silent-except` was triaged by reading, not exhaustively; the 52 remain a list
  to revisit, not a clean bill.

## Next

Remaining backlog work is behavioural, not cosmetic: prompt-author wiring, ad
copy fitting, image parameter tuning, credit consumption, and the `serviceGate`
decision. Those need a design decision recorded before they can be dispatched,
which is why they sit in `needs-author` rather than in the queue as guesses.
