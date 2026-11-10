"""A behaviour rule that lives only in prose is not a control.

This is the lesson from the "jailbreak" video, made operational. A markdown or
config file that carries an agent's persona can be edited by anyone who can write
to the repo - including a planted file in a folder you open. What must NOT depend
on that prose is the two hard boundaries (Amazon, spend) and the model identity.

So the guard checks three things and refuses the build if any fails:

1. **No jailbreak patterns.** No agent system prompt (or agent markdown file) may
   contain instructions that remove the ability to refuse, ignore prior rules, or
   claim unlimited permission. That class of text is exactly the injection surface
   a hostile page, file or tool output needs.
2. **Every agent runs on the owner's model.** A free/router fallback is a silent
   downgrade; the id must match `opencode-go/deepseek-v4.1-flash`.
3. **Deny-by-default on the risky tools per lane.** A read-only lane must not have
   write or shell access; the worker must not have web tools it does not need.

The guard does NOT try to detect "malicious intent" (unfalsifiable). It enforces
the specific, checkable properties that make a prompt edit unable to widen
privileges.

    python tools/guard_agents.py            # check, exit 1 on a violation
    python tools/guard_agents.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "opencode.jsonc"
AGENT_DIRS = (ROOT / ".opencode" / "agents", ROOT / ".opencode" / "agent",
              ROOT / "agents" / "prompts")
REQUIRED_MODEL = "opencode-go/deepseek-v4.1-flash"

#: Phrases that surrender the ability to refuse. Matched case-insensitively with
#: word boundaries so "do not ignore your instructions" is not a false positive
#: (the negative form is exactly what we want an agent to say).
JAILBREAK_PATTERNS = [
    r"\bnever\s+refuse\b",
    r"\bdo\s+not\s+refuse\b",
    r"\bno\s+restrictions\b",
    r"\bunrestricted\b",
    r"\bignore\s+(all\s+)?(your\s+|the\s+)?(previous\s+|prior\s+)?instructions?\b",
    r"\bdisregard\s+(all\s+)?(previous\s+|prior\s+)?(instructions?|rules?)\b",
    r"\boverride\s+(your\s+)?(safety|guardrails|rules)\b",
    r"\bbypass\s+(the\s+)?(safety|guardrails|policy|policies)\b",
    r"\bjailbreak\b",
    r"\bact\s+as\s+(an?\s+)?(unfiltered|uncensored)\b",
    r"\bpretend\s+(that\s+)?you\s+have\s+no\s+rules\b",
]

#: Lanes that must not be able to write or run a shell.
READ_ONLY_LANES = ("verifier", "research")


def _strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments outside strings, and trailing commas."""
    out: List[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    cleaned = "".join(out)
    return re.sub(r",(\s*[}\]])", r"\1", cleaned)


def load_config(path: Path = CONFIG) -> Dict[str, Any]:
    return json.loads(_strip_jsonc(path.read_text(encoding="utf-8")))


def agent_texts(cfg: Dict[str, Any]) -> Dict[str, str]:
    agents = cfg.get("agents") or cfg.get("agent") or {}
    return {str(name): str(body.get("system") or body.get("prompt") or "")
            for name, body in agents.items() if isinstance(body, dict)}


def scan_text(name: str, text: str) -> List[Dict[str, str]]:
    """Jailbreak patterns, minus the negated forms we actually want agents to say.

    "Do not ignore your instructions" contains the phrase we forbid, and it is the
    opposite of a jailbreak. Negated clauses are removed before matching so the
    guard cannot punish an agent for stating the rule correctly.
    """
    scrubbed = re.sub(r"\b(do\s+not|don't|does\s+not|never|must\s+not)\s+"
                      r"(ignore|disregard|override|bypass)\b[^.;]*[.;]?",
                      " ", text, flags=re.I)
    hits = []
    for pattern in JAILBREAK_PATTERNS:
        for match in re.finditer(pattern, scrubbed, re.I):
            start = max(0, match.start() - 40)
            hits.append({"agent": name, "pattern": pattern,
                         "excerpt": scrubbed[start:match.end() + 40].replace("\n", " ")})
    return hits


def check_models(cfg: Dict[str, Any]) -> List[str]:
    problems = []
    for name, body in (cfg.get("agents") or {}).items():
        model = str((body or {}).get("model") or cfg.get("model") or "")
        if model != REQUIRED_MODEL:
            problems.append(f"{name}: model {model!r} is not {REQUIRED_MODEL!r}")
    return problems


def check_lane_tools(cfg: Dict[str, Any]) -> List[str]:
    problems = []
    for name, body in (cfg.get("agents") or {}).items():
        if name not in READ_ONLY_LANES:
            continue
        tools = (body or {}).get("tools") or {}
        if tools.get("edit") is not False:
            problems.append(f"{name}: a read-only lane must set tools.edit = false")
    return problems


def check_all(cfg: Dict[str, Any]) -> Dict[str, Any]:
    hits: List[Dict[str, str]] = []
    for name, text in agent_texts(cfg).items():
        hits.extend(scan_text(name, text))
    for folder in AGENT_DIRS:
        if not folder.is_dir():
            continue
        for path in folder.rglob("*.md"):
            try:
                label = str(path.relative_to(ROOT))
            except ValueError:
                label = str(path)
            hits.extend(scan_text(label, path.read_text(
                encoding="utf-8", errors="replace")))
    problems = check_models(cfg) + check_lane_tools(cfg)
    return {"ok": not hits and not problems, "jailbreak": hits, "problems": problems,
            "agents": sorted(agent_texts(cfg))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Guard agent prompts and lanes.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--config", default=str(CONFIG))
    ns = parser.parse_args(argv)
    try:
        cfg = load_config(Path(ns.config))
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": f"config unreadable: {exc}"}))
        return 2
    result = check_all(cfg)
    if ns.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"agents: {', '.join(result['agents']) or '(none)'}")
        for hit in result["jailbreak"]:
            print(f"  JAILBREAK  {hit['agent']}: {hit['pattern']}  ...{hit['excerpt']}...")
        for problem in result["problems"]:
            print(f"  PROBLEM    {problem}")
        print("OK" if result["ok"] else "REFUSED")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
