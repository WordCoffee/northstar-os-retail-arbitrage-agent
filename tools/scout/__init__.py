"""Discovery lane — D11 (A18–A21).

Scouts search public code/model/package/paper indexes for things Northstar
services could adopt, vet them, and write ranked evidence-backed findings to
``ty/intel_gaps.json``.

    A18  registry + connectors   config.py, connectors/
    A19  normaliser + licences   normalize.py, licence.py, refusal log
    A20  evidence extractor      evidence.py (repo anchors; media is another lane)
    A21  gap matcher + yield     rank.py (scoring, hypotheses, gap list)
    —    vetting + status        vet.py (tools/vet_package.py adapter)

Run ``python -m tools.scout.collect --dry-run`` first; it replays fixtures and
writes nothing.
"""
from __future__ import annotations

__all__ = ["config", "licence", "normalize", "evidence", "rank", "vet", "verify"]
