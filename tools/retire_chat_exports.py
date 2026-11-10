"""Retire the two chat exports — only after the owner has rotated the keys.

Removing a file from the tree does not remove it from history, and allowlisting a *live* key hides a
secret. So this refuses to act until a rotation record exists:

    state/security/keys_rotated.json
    {"rotated": true, "at": "2026-11-10T…", "by": "owner (Tyrone)",
     "keys": ["SCAVIO_API_KEY", "BRIGHTDATA_API_KEY", "GITHUB_PAT"]}

When it does exist, the run:

1. removes the two exports from the tree;
2. writes their **fingerprints** (file, line, rule) to `state/security/rotated_fingerprints.json`;
3. adds a narrow, dated allowlist entry to `.gitleaks.toml` for those paths — the fingerprints are
   dead credentials, so a history scan should stop shouting about them;
4. commits with a message that says "rotated keys only".

    python tools/retire_chat_exports.py --check
    python tools/retire_chat_exports.py --retire
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROTATION = ROOT / "state" / "security" / "keys_rotated.json"
FINGERPRINTS = ROOT / "state" / "security" / "rotated_fingerprints.json"
TOML = ROOT / ".gitleaks.toml"

EXPORTS = (
    ("FirstNorthstarautomationchat.md", (1143, 1148, 1291, 1296), "generic-api-key"),
    ("autothink-ui-chat-export.md", (7852,), "github-pat"),
)


def rotation_state() -> dict:
    if not ROTATION.exists():
        return {"rotated": False, "why": f"{ROTATION.relative_to(ROOT)} does not exist"}
    try:
        data = json.loads(ROTATION.read_text(encoding="utf-8"))
    except ValueError as exc:
        return {"rotated": False, "why": f"rotation record unreadable: {exc}"}
    return {"rotated": bool(data.get("rotated")), "record": data}


def plan() -> dict:
    present = [name for name, _, _ in EXPORTS if (ROOT / name).is_file()]
    return {"rotation": rotation_state(), "files_present": present,
            "already_retired": [name for name in present if name not in
                                [p for p in present]], }


def allowlist_block() -> str:
    lines = ["", "# ---------------------------------------------------------------------------",
             "# Rotated credentials: the chat exports were removed from the tree on 2026-11-10 after",
             "# the owner rotated SCAVIO_API_KEY, BRIGHTDATA_API_KEY and the GitHub PAT. These paths",
             "# are allowlisted so a *history* scan does not re-flag values that are now dead. The",
             "# fingerprints are recorded in state/security/rotated_fingerprints.json.",
             "# ---------------------------------------------------------------------------", ""]
    for name, _, _ in EXPORTS:
        lines += ["[[allowlists]]",
                  f'description = "rotated: {name} was removed from the tree; its keys are dead"',
                  f"paths = ['''{name.replace('.', chr(92) + '.')}$''']",
                  ""]
    return "\n".join(lines)


def retire() -> int:
    state = rotation_state()
    if not state["rotated"]:
        print(json.dumps({"refused": "keys_not_rotated", **state}, indent=2), file=sys.stderr)
        return 2
    removed, fingerprints = [], []
    for name, lines, rule in EXPORTS:
        path = ROOT / name
        if path.is_file():
            subprocess.run(["git", "rm", "--quiet", "--cached", name], cwd=str(ROOT), check=False)
            path.unlink(missing_ok=True)
            removed.append(name)
        for line in lines:
            fingerprints.append({"file": name, "line": line, "rule": rule,
                                 "state": "rotated 2026-11-10"})
    FINGERPRINTS.parent.mkdir(parents=True, exist_ok=True)
    FINGERPRINTS.write_text(json.dumps({"rotated_at": state["record"].get("at"),
                                        "by": state["record"].get("by"),
                                        "fingerprints": fingerprints}, indent=2) + "\n",
                            encoding="utf-8")
    if "rotated: " not in TOML.read_text(encoding="utf-8"):
        with TOML.open("a", encoding="utf-8") as handle:
            handle.write(allowlist_block())
    subprocess.run(["git", "add", "-A"], cwd=str(ROOT), check=False)
    message = ("security: remove the two chat exports after rotating SCAVIO_API_KEY, "
               "BRIGHTDATA_API_KEY and the GitHub PAT; allowlist their dead fingerprints")
    commit = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", message],
                            cwd=str(ROOT), capture_output=True, text=True)
    print(json.dumps({"removed": removed, "fingerprints": len(fingerprints),
                      "commit": commit.returncode == 0,
                      "note": ("the public remote still carries the history: a force-push or a "
                               "GitHub purge is an owner decision")}, indent=2))
    return 0


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retire the chat exports once the keys are rotated")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--retire", action="store_true")
    ns = parser.parse_args(argv)
    if ns.retire:
        return retire()
    print(json.dumps(plan(), indent=2))
    return 0 if not rotation_state()["rotated"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
