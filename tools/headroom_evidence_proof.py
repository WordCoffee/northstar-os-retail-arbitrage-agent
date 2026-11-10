"""Evidence-integrity proof for Headroom, run before it is allowed near the loop.

Headroom compresses context lossily. The continuous build loop's hard rule is that
a card is DONE only on real command output, so the adoption gate is narrow and
mechanical: **compression must not drop a FAILED/ERROR line or the test counts.**

Runs in the headroom venv, not the backend venv:

    python tools/headroom_evidence_proof.py <logfile> [--model deepseek-v4]

Exit code 0 = evidence survived, 1 = it did not, 2 = headroom unavailable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: Lines that must survive byte-for-byte (after strip) for the proof to pass.
FAIL = re.compile(r"^(FAILED|ERROR)\s", re.MULTILINE)
SUMMARY = re.compile(r"^(=+\s*)?(\d+ (passed|failed|skipped|error))", re.MULTILINE)


def _text_of(result) -> str:
    msgs = getattr(result, "messages", None)
    if msgs is None and isinstance(result, dict):
        msgs = result.get("messages")
    if not msgs:
        return ""
    out = []
    for m in msgs:
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if isinstance(content, list):
            content = " ".join(str(part.get("text", part)) if isinstance(part, dict) else str(part)
                               for part in content)
        out.append(str(content))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile")
    ap.add_argument("--model", default="deepseek-v4")
    ap.add_argument("--limit", type=int, default=6000, help="force compression with a small window")
    args = ap.parse_args()

    try:
        from headroom import compress
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "reason": "headroom_unavailable", "error": str(exc)}))
        return 2

    raw = Path(args.logfile).read_text(encoding="utf-8", errors="replace")
    expected_fail = sorted({m.group(0).strip() for m in FAIL.finditer(raw)})
    expected_summary = sorted({m.group(2).strip() for m in SUMMARY.finditer(raw)})

    result = compress([{"role": "user", "content": raw}],
                      model=args.model, model_limit=args.limit, optimize=True)
    packed = _text_of(result)

    got_fail = sorted({m.group(0).strip() for m in FAIL.finditer(packed)})
    got_summary = sorted({m.group(2).strip() for m in SUMMARY.finditer(packed)})

    missing_fail = [line for line in expected_fail if line not in packed]
    missing_summary = [s for s in expected_summary if s not in packed]

    verdict = {
        "ok": not missing_fail and not missing_summary,
        "chars_before": len(raw),
        "chars_after": len(packed),
        "ratio": round(len(packed) / len(raw), 3) if raw else None,
        "failed_lines_expected": expected_fail,
        "failed_lines_lost": missing_fail,
        "summaries_expected": expected_summary,
        "summaries_lost": missing_summary,
        "model": args.model,
    }
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
