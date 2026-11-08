"""Merge a batch of agent visual-review verdicts into image_audit_verdicts.json."""
import json
from pathlib import Path
import sys

V = Path("out_lions_mane/image_audit_verdicts.json")

BATCH = {
    # edit this dict per batch, then run: python write_verdicts.py
}

if __name__ == "__main__":
    data = json.loads(V.read_text(encoding="utf-8")) if V.exists() else {}
    data.update(BATCH)
    V.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"merged batch of {len(BATCH)}; total verdicts: {len(data)}")
    print("audited:", ", ".join(BATCH.keys()))
