"""Arm the local media lane in .env without ever reading a value out loud.

`MEDIA_GEN_LIVE` is a routing flag, not a secret (AGENTS.md §3.1 non-secret config
keys). This script rewrites only that one line, prints nothing from the file, and
reports what it did. An existing line is edited in place because python-dotenv is
loaded with override=False: a duplicate appended at the bottom would be ignored.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
ENV = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\.env")
KEY = "MEDIA_GEN_LIVE"
VALUE = "1"

if not ENV.is_file():
    print("no .env at the repo root; nothing changed")
    raise SystemExit(2)

raw = ENV.read_bytes()
text = raw.decode("utf-8", "surrogateescape")
lines = text.splitlines(keepends=True)

hits = [i for i, line in enumerate(lines) if line.split("=", 1)[0].strip() == KEY]
if hits:
    i = hits[0]
    eol = "\r\n" if lines[i].endswith("\r\n") else "\n"
    lines[i] = f"{KEY}={VALUE}{eol}"
    action = "updated in place"
else:
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += "\n"
    lines.append(f"{KEY}={VALUE}\n")
    action = "appended"

ENV.write_bytes("".join(lines).encode("utf-8", "surrogateescape"))
print(f"{KEY}: {action} -> {VALUE}; duplicates present: {max(0, len(hits) - 1)}")
