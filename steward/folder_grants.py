"""Folder Grants — Tier 1.

Per charter §4.2: allowlisted roots, read/write modes, deny list
(browser profile, cookie stores, password stores, SSH/key files, system dirs).

Tier 1 only: these rules and thresholds are editable by Ty with snapshot,
tests, auto-revert. Tier 2 (kill switch, watchdog, ledger, policy bundle
hashes, approval channel) is owner-gated — see steward/watchdog.py.
"""

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED = REPO_ROOT / "shared" / "steward"
SHARED.mkdir(parents=True, exist_ok=True)

# --- Allowlisted roots (Tier 1: Ty may edit with snapshot) ---
ALLOWLISTED_ROOTS = [
    str(REPO_ROOT / "Northstar_backend"),
    str(REPO_ROOT / "northstar-os-ui"),
    str(REPO_ROOT / "docs"),
    str(REPO_ROOT / "reports"),
    str(REPO_ROOT / "shared"),
    str(REPO_ROOT / "steward"),
]

# --- Deny list (Tier 1: paths always blocked, no matter grant) ---
DENY_PATHS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    ".ssh",
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
    "id_rsa",
    "id_ed25519",
]

# Deny dirs (never read or write into): browser profile, cookie stores, password stores, system dirs
DENY_DIRS = [
    "AppData\\Local\\Google\\Chrome\\User Data",
    "AppData\\Roaming\\Mozilla",
    "AppData\\Roaming\\Microsoft\\Protect",
    "AppData\\Roaming\\Microsoft\\Credentials",
    "Application Data\\Microsoft\\Protect",
    "Application Data\\Microsoft\\Credentials",
    "AppData\\Local\\Mozilla",
]

QUARANTINE_DIR = SHARED / "quarantine"
QUARANTINE_RETENTION_DAYS = 30

SNAPSHOTS_DIR = SHARED / "grants_snapshots"
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

TRUST_LEVELS = ["read_only", "reversible_write", "external_write"]
TRUST_STEPS = {"read_only": 0, "reversible_write": 1, "external_write": 2}


@dataclass
class FolderGrant:
    root: str
    read: bool = True
    write: bool = False
    trust: str = "read_only"
    granted_by: str = "owner"
    granted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return {
            "root": self.root,
            "read": self.read,
            "write": self.write,
            "trust": self.trust,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
        }


def _resolve_root(path: str) -> Optional[Path]:
    p = Path(path).resolve()
    for root in ALLOWLISTED_ROOTS:
        root_path = Path(root).resolve()
        try:
            rel = p.relative_to(root_path)
            # Path is inside allowlisted root
            return root_path
        except ValueError:
            continue
    return None


def _is_denied(path: str) -> bool:
    p = Path(path).resolve()
    name = p.name.lower()
    for pattern in DENY_PATHS:
        pat = pattern.lower()
        if "*" in pat:
            import fnmatch
            if fnmatch.fnmatch(name, pat):
                return True
        elif name == pat:
            return True
    # Check deny dirs
    full = str(p)
    for dd in DENY_DIRS:
        if dd.lower() in full.lower():
            return True
    return False


def check_grant(path: str) -> dict:
    """Check whether a path operation is permitted.

    Returns dict with: allowed (bool), reason (str), trust (str).
    """
    if _is_denied(path):
        return {"allowed": False, "reason": "DENY_PATH", "trust": "none"}

    root = _resolve_root(path)
    if root is None:
        return {"allowed": False, "reason": "NOT_ALLOWLISTED", "trust": "none"}

    return {"allowed": True, "reason": "ALLOWED_IN_ROOT", "trust": "read_only"}


def snapshot_write(src: str, label: str = "grant") -> Optional[Path]:
    """Take a snapshot copy of a file before a write operation.

    Per charter §4.2: snapshot before every write.
    Stored in shared/steward/grants_snapshots/; TTL 30 days.
    """
    src_path = Path(src).resolve()
    if not src_path.exists() or not src_path.is_file():
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = src_path.name.replace("/", "_").replace("\\", "_")
    snap_name = f"{ts}_{label}_{safe_name}"
    snap_dir = SNAPSHOTS_DIR / label
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / snap_name
    shutil.copy2(src_path, snap_path)
    # Record
    meta = {
        "original": str(src_path),
        "snapshot": str(snap_path),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "ttl_days": QUARANTINE_RETENTION_DAYS,
    }
    (snap_dir / (snap_name + ".meta")).write_text(json.dumps(meta, indent=2))
    return snap_path


def quarantine_delete(path: str) -> Path:
    """Move a file to 30-day delete quarantine instead of immediate delete.

    Per charter §4.2: 30-day delete quarantine.
    Returns the quarantine path.
    """
    src = Path(path).resolve()
    if not src.exists():
        return None

    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = src.name.replace("/", "_").replace("\\", "_")
    dest = QUARANTINE_DIR / f"{ts}_{safe_name}"
    shutil.move(str(src), str(dest))
    return dest
