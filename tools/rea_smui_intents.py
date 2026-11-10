"""
REA 1.6 instrument — mine the real chat corpus for simple-mode intents.

Aggregate counts only. No message text is copied into the report; the only
verbatim strings kept are tool names and the sample size. This keeps operator
content out of a research artifact while still producing measured numbers.

Output: reports/rea_probe/smui_intents.json
"""

from __future__ import annotations

import collections
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "Northstar_backend" / "data" / "northstar.db"
OUT = ROOT / "reports" / "rea_probe"
OUT.mkdir(parents=True, exist_ok=True)

INTENT_RULES = [
    ("label / pouch composite", r"\b(label|pouch|bag|dieline|composite|wrap)\b"),
    ("image render", r"\b(render|generate|image|plate|mockup|photo)\b"),
    ("edit / variation", r"\b(edit|variation|change the|swap|recolor|recolour)\b"),
    ("A+ / listing content", r"\b(a\+|aplus|listing|bullet|caption|description)\b"),
    ("social asset", r"\b(instagram|tiktok|pinterest|social|reel|story)\b"),
    ("video", r"\b(video|ad|clip|voiceover|narration)\b"),
    ("logo / brand mark", r"\b(logo|brand|wordmark|lockup)\b"),
    ("print / export", r"\b(print|pdf|export|zip|svg)\b"),
    ("status / help", r"\b(what|why|how|status|help|error|failed)\b"),
]


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    def one(sql: str) -> int:
        row = con.execute(sql).fetchone()
        return int(row[0]) if row else 0

    cols = {r["name"] for r in con.execute("pragma table_info(chat_messages)")}
    role_col = "role" if "role" in cols else None
    content_col = next((c for c in ("content", "text", "body") if c in cols), None)

    totals = {
        "chat_sessions": one("select count(*) from chat_sessions"),
        "chat_messages": one("select count(*) from chat_messages"),
        "chat_runs": one("select count(*) from chat_runs"),
        "chat_tool_calls": one("select count(*) from chat_tool_calls"),
    }

    tool_counts = [
        {"tool": r["name"], "calls": r["c"]}
        for r in con.execute(
            "select coalesce(name,'?') name, count(*) c from chat_tool_calls "
            "group by 1 order by 2 desc limit 25")
    ]

    per_session = [
        {"session": r["session_id"], "messages": r["c"], "tool_calls": r["t"] or 0}
        for r in con.execute(
            "select m.session_id, count(*) c, "
            "(select count(*) from chat_tool_calls t where t.session_id = m.session_id) t "
            "from chat_messages m group by 1 order by 2 desc limit 20")
    ]

    intents = collections.Counter()
    user_msgs = 0
    if role_col and content_col:
        for row in con.execute(
                f"select {content_col} c from chat_messages where lower({role_col})='user'"):
            text = (row["c"] or "").lower()
            if not text.strip():
                continue
            user_msgs += 1
            for name, pat in INTENT_RULES:
                if re.search(pat, text):
                    intents[name] += 1

    tools_per_session = (
        round(totals["chat_tool_calls"] / totals["chat_sessions"], 2)
        if totals["chat_sessions"] else None)
    msgs_per_session = (
        round(totals["chat_messages"] / totals["chat_sessions"], 2)
        if totals["chat_sessions"] else None)

    data = {
        "probe": "rea_smui_intents",
        "date": "2026-10-28",
        "source_db": str(DB.relative_to(ROOT)),
        "totals": totals,
        "user_messages_scanned": user_msgs,
        "messages_per_session": msgs_per_session,
        "tool_calls_per_session": tools_per_session,
        "intent_counts": intents.most_common(),
        "tool_usage": tool_counts,
        "busiest_sessions": per_session,
        "caveat": ("Counts are keyword matches over user turns, not classified intents. "
                   "A turn can match more than one rule. No message text is stored here."),
    }
    (OUT / "smui_intents.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in data.items() if k != "busiest_sessions"}, indent=2))


if __name__ == "__main__":
    main()
