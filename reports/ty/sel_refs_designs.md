# sel-refs-designs — a licence-checked reference library, not a download folder

Job `sel-refs-designs` (rank 4). Rollback tag `rollback/pre-sel06b-20261111` (same session, tree).

## The defect

The rubric had nowhere to come from. Work order PATCH 1 forbids asking the owner for examples; PATCH 2
adds **Openverse** as a rubric source and says each work's licence must be verified before use. The
library was 21 stored rows over **2 distinct product designs**, so every "stored reference" brief was
a variant of the same bag.

## What was built

`tools/reference_scout.py` — Openverse API v1, no key, loopback-free but non-Amazon:

| rule | why |
|---|---|
| only `cc0`, `by`, `by-sa` | `by-nc` forbids commercial use, `by-nd` forbids modification; a rubric image that cannot be shown or adapted is not usable. Refused **by name**, counted, never silently dropped |
| a landing URL is mandatory | the licence must be verifiable at source; a row without one is refused |
| ≥ 700 px on the short side | a 320 px thumbnail cannot support a print-quality rubric |
| a packaging word in title/tags/description | Openverse's relevance is loose: the first run returned a 1960s airline flyer for "stand up pouch packaging". Six rows were refused `off_topic` |
| the file must open as an image, measured | "it downloaded" is not "it is a picture"; the tool records the **actual** size and deletes what will not open |
| every row says `usage: rubric reference only` | never a product asset, never composited into a seller picture |

`--vision` asks the local model (`gemma3:4b`, loopback) one question per row — *is a package the
subject of this picture?* — and records the verdict beside the row, because keyword relevance is not
evidence.

## Measured run

`python tools/reference_scout.py --per-query 4 --min-side 700 --vision`

- **17 kept** of 68 candidates: 51 refused, split `too small` 37 · `download failed` 8 · `off_topic` 6.
- **7 packaging families** with at least one row: coffee bag, gift box, tea tin, soap box, spice jar,
  skincare bottle, packaging mockup.
- Licences: `by` 7, `cc0` 5, `by-sa` 4 — every row carries creator, licence version, licence URL and
  the source page.
- Every file opened as an image; measured sizes recorded (short side 682–1024 px).
- **Vision: 17/17 confirmed as a package.** Recorded, and discounted: the same judge passed a flat
  studio sweep as a "light oak kitchen counter in morning light" earlier in this session
  (`reports/ty/sel07_bundle_units.md`), so a judge that has not yet said *no* to anything is weak
  evidence. It is reported as measured, not as proof.

Manifest: `reports/ty/reference_library.json`; readable table `reports/ty/reference_library.md`;
images in `renders/references/public/` (local, git-ignored — a fresh checkout rebuilds them with the
tool, and the manifest is the record of what was there and under which licence).

**Honest limit:** "7 families" counts queries, not a human judgement of design quality, and the vision
verdict is a 4B model's yes/no. Both are recorded per row so a later pass can prune without re-crawling.

## Tests

`pytest Northstar_backend/test_reference_scout.py -q` → **8 passed** (licence kept/refused by name,
missing source URL, tiny image, off-topic row, the recorded licence/usage fields, a network failure
recorded not hidden, a too-small download refused, the API query carries the licence filter).
