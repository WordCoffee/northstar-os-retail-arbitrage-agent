"""Temp: probe 9B encoder with tiny vs the real sanitized MOGRA prompt."""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import studio_generation as sg  # noqa: E402
import text_fidelity as tf  # noqa: E402

st = sg.engine_status()
print("armed:", st.get("armed"), "| reachable:", st.get("reachable"))
if not st.get("armed"):
    print("engine not armed; abort probe")
    sys.exit(1)

try:
    out = sg.generate_image(prompt="matte forest-green stand-up pouch, studio light",
                            width=768, height=768, tier="draft")
    print("TINY OK:", out["model"], len(out["bytes"]))
except Exception as exc:  # noqa: BLE001
    print("TINY FAILED:", str(exc)[:400])
    sys.exit(1)

# real sanitized prompt from the stored MOGRA brief
c = sqlite3.connect(str(ROOT / "data" / "northstar.db"))
c.row_factory = sqlite3.Row
brief = None
for t in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE name LIKE '%asset%'")]:
    try:
        row = c.execute(f"SELECT metadata FROM {t} WHERE storage_key = ?",
                        ("36357d08be864c6491f1195f8bcb1262.png",)).fetchone()
    except Exception:
        continue
    if row:
        md = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {})
        brief = (md.get("generation") or {}).get("prompt")
        break
prep = tf.prepare_render_brief(brief, True)
prompt = prep["brief"]
print(f"sanitized prompt: {len(prompt)} chars")
try:
    out2 = sg.generate_image(prompt=prompt, width=768, height=768, tier="draft")
    print("LONG OK:", out2["model"], len(out2["bytes"]))
except Exception as exc:  # noqa: BLE001
    print("LONG FAILED:", str(exc)[:800])
