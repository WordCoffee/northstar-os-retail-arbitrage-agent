# Continuous Improvement Engine (CIE)

Bojo and Autothink get better every night, from evidence, without a human in the
loop — until the operator stops it.

## What one cycle does

```
snapshot → observe → prioritise → research → author → evaluate → promote → report
```

- **Observe** — golden-set questions the packs cannot answer, plus operator
  feedback from the Bojo receipt row (`Right` / `Wrong`) and `corrected` ratings.
  Nothing is invented: a gap always points at a question or a rating.
- **Prioritise** — domain weight × frequency, capped at 5 gaps per cycle.
- **Research** — retrieves a curated snippet (`knowledge/sources/corpus.jsonl`)
  with its source, date and do/don't pair. No free-form model invention.
- **Author** — validates the atom and rejects duplicates/near-duplicates.
- **Evaluate** — coverage before/after on the golden set. A promoted atom must
  close at least one gap.
- **Promote** — appends to `knowledge/<domain>/atoms.json`, bumps the pack
  version, writes `reports/improvement/cycles/<id>.md` with the rollback.
- **Report** — every cycle is auditable; rejected candidates keep their reasons.

## Commands

```powershell
cd Northstar_backend
python -m cie_loop --status          # packs, coverage, open gaps, last cycle
python -m cie_loop --cycle --dry-run # evaluate only, never writes
python -m cie_loop --cycle           # one real cycle
python -m cie_loop --cycle --live --live-limit 10   # also grade real answers
python -m cie_loop --stop            # stop switch (same as the UI button)
python -m cie_loop --resume
```

`--live` asks the model the golden questions and grades the answers with the
deterministic graders. It is a **quality trend, not the promotion gate**: a bad
model day must never rewrite selling rules. Results land in the `evals` table and
the cycle report.

Scheduled wrapper: `tools/improvement_cycle.ps1` (refuses to run when stopped).

```
schtasks /Create /SC DAILY /ST 02:00 /TN NorthstarOS-Improvement ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"<repo>\tools\improvement_cycle.ps1\"" /F
```

## API

`GET  /api/v1/improvement/status` · `/queue` · `/cycles` · `/packs` · `/atoms`
`POST /api/v1/improvement/cycle` (`{"dry_run": true}` by default) · `/stop` · `/resume` · `/feedback`

## Where knowledge reaches the model

`chat_adapter.build_chat_messages(query=...)` retrieves the top rules for the
turn (`knowledge_pack.retrieve`, deterministic token overlap) and appends them to
the system prompt as `DO` / `DON'T` pairs with source and effective date. A
retrieval failure returns `""` and never breaks a turn.

## Rollback

Every promotion is a file change under `knowledge/`. The cycle record stores the
command:

```powershell
git checkout -- knowledge/     # restore every pack to the base commit
```

A per-atom rollback is deleting the atom from `knowledge/<domain>/atoms.json` and
running `python -m cie_loop --status` to confirm the version moved.

## Stop switch

`state/improvement/STOP` (file) or the Improvement room button. Checked before
every stage; a cycle halts at the next boundary, never mid-write.

## Current limits (honest)

- Research is **corpus retrieval**, not crawling. An online fetcher can append to
  `knowledge/sources/corpus.jsonl`; the atom contract does not change.
- Coverage is measured against declared `expects` on golden items, not against
  live answer quality. Live grading (`cie_eval.run_suite` with an answer
  function) is wired and tested but not yet part of the nightly cycle.
- Seed atoms are marked `needs_verification: true`. They must be checked against
  the current Seller Central page before a customer-facing claim relies on them.
