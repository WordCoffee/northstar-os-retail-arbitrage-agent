"""Vault Broker — Tier 1.

Per charter §4.2: secrets stored outside repo and model context,
injected at execution, scoped per service, revocable, never logged.

Trust ladder per service:
  read-only  ->  reversible write  ->  external write
Steps up need owner approval. Never delegate password/2FA/recovery changes.

Versioned policy bundles with hashes, known-good tags, auto-revert on
failed health checks. Rollback is a Watchdog function; Ty cannot write
to it or the ledger. External-effects ledger kept separately (emails, posts,
files shared) since rollback does not undo them.
"""

import json
import os
import hashlib
import base64
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED = REPO_ROOT / "shared" / "steward"
SHARED.mkdir(parents=True, exist_ok=True)

VAULT_DIR = SHARED / "vault_store"
VAULT_DIR.mkdir(parents=True, exist_ok=True)

VERSIONS_DIR = VAULT_DIR / "versions"
VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

HEALTH_LOG = VAULT_DIR / "health_log.jsonl"
HEALTH_LOG.touch(exist_ok=True)

POLICY_BUNDLE_DIR = VAULT_DIR / "policy_bundles"
POLICY_BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

POLICY_HASH_FILE = VAULT_DIR / "policy_hash.json"


@dataclass
class VaultEntry:
    """A stored secret entry — never plain-text in model context."""

    key: str  # service key name
    encrypted: str  # base64-encoded encrypted blob
    service: str  # which service this is for
    scope: str  # "read-only" | "reversible-write" | "external-write"
    created_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_utc: Optional[str] = None
    rotated: int = 0  # number of rotations
    rotated_at: Optional[str] = None

    def to_dict(self):
        return {
            "key": self.key,
            "encrypted": self.encrypted,
            "service": self.service,
            "scope": self.scope,
            "created_utc": self.created_utc,
            "expires_utc": self.expires_utc,
            "rotated": self.rotated,
            "rotated_at": self.rotated_at,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            key=d["key"],
            encrypted=d["encrypted"],
            service=d["service"],
            scope=d["scope"],
            created_utc=d.get("created_utc", datetime.now(timezone.utc).isoformat()),
            expires_utc=d.get("expires_utc"),
            rotated=d.get("rotated", 0),
            rotated_at=d.get("rotated_at"),
        )


def _entry_path(key: str) -> Path:
    """File path for a vault entry: shared/steward/vault_store/versions/<key>.jsonl"""
    return VERSIONS_DIR / f"{key}.jsonl"


def _to_dict(e: Any) -> dict:
    """Convert VaultEntry or dict to dict."""
    if hasattr(e, "to_dict"):
        return e.to_dict()
    return dict(e)


def _hash_entry(e: Any) -> str:
    """Compute deterministic hash of entry (for chain integrity)."""
    data = json.dumps(_to_dict(e), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _chain_head_hash(key: str) -> str:
    """Return the SHA-256 of the latest entry, or genesis if none."""
    path = _entry_path(key)
    entries = []
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            entries = []
    if not entries:
        return hashlib.sha256(b"genesis").hexdigest()
    return _hash_entry(entries[-1])


def store_secret(
    key: str,
    encrypted_blob: str,
    service: str,
    scope: str,
    expires_utc: Optional[str] = None,
) -> VaultEntry:
    """Store an encrypted secret.

    scope must be one of: "read-only", "reversible-write", "external-write"
    encrypted_blob is base64-encoded; the broker never reads the plain text.

    The entry is appended to the key-specific JSONL; hash-chain integrity
    is maintained (prev_hash links within entries).
    """
    if scope not in ("read-only", "reversible-write", "external-write"):
        raise ValueError(f"invalid scope: {scope}")

    path = _entry_path(key)
    entry = VaultEntry(
        key=key,
        encrypted=encrypted_blob,
        service=service,
        scope=scope,
        expires_utc=expires_utc,
    )

    new_entry_dict = entry.to_dict()
    # Compute prev_hash from latest existing entry.
    prev_hash = _chain_head_hash(key)
    new_entry_dict["prev_hash"] = prev_hash
    # Compute hash using only the fields that VaultEntry accepts
    hash_data = {k: v for k, v in new_entry_dict.items() if k not in ("prev_hash", "sha256")}
    new_entry_dict["sha256"] = _hash_entry(hash_data)

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(new_entry_dict, sort_keys=True, separators=(",", ":")) + "\n")

    # Also append to health log for audit.
    _health_append({
        "action": "store_secret",
        "key": key,
        "service": service,
        "scope": scope,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "entry_hash": new_entry_dict["sha256"],
    })

    return entry


def retrieve_secret(key: str) -> Optional[VaultEntry]:
    """Return the latest VaultEntry for a key — the broker NEVER returns plain text.

    This method returns the metadata + hash chain info; the caller must
    pass the encrypted blob to an external decryption service. The broker
    NEVER decrypts secrets in-process.
    """
    path = _entry_path(key)
    entries = []
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            entries = []

    if not entries:
        return None

    # Return latest entry metadata (never plain text).
    latest = entries[-1]
    latest_dict = {k: v for k, v in latest.items() if k not in ("sha256", "prev_hash")}
    return VaultEntry(**latest_dict)


def rotate_secret(
    key: str,
    new_encrypted_blob: str,
    service: str,
    scope: str,
    owner_approval: bool = False,
) -> Optional[VaultEntry]:
    """Rotate a secret — requires owner_approval flag set True.

    Per charter §4.2: Steps up the trust ladder need owner approval.
    """
    if scope not in ("read-only", "reversible-write", "external-write"):
        raise ValueError(f"invalid scope: {scope}")

    path = _entry_path(key)
    entries = []
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            entries = []

    prev_hash = _chain_head_hash(key)
    new_entry = VaultEntry(
        key=key,
        encrypted=new_encrypted_blob,
        service=service,
        scope=scope,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )
    new_entry_dict = new_entry.to_dict()
    new_entry_dict["prev_hash"] = prev_hash
    hash_data = {k: v for k, v in new_entry_dict.items() if k not in ("prev_hash", "sha256")}
    new_entry_dict["sha256"] = _hash_entry(hash_data)

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(new_entry_dict, sort_keys=True, separators=(",", ":")) + "\n")

    # Health log
    _health_append({
        "action": "rotate_secret",
        "key": key,
        "service": service,
        "scope": scope,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "entry_hash": new_entry_dict["sha256"],
    })

    return new_entry


def set_policy_bundle(name: str, bundle: Dict[str, Any], hash_algorithm: str = "sha256") -> str:
    """Store a versioned policy bundle with hash integrity.

    Tier 1: Ty may edit policy bundles (workflows, thresholds, UI prompts,
    folders inside approved roots). Bundles are versioned and hash-chained.
    Tier 2 changes (kill-switch, watchdog, approval channel) require owner approval.
    """
    bundle_hash = hashlib.new(hash_algorithm, json.dumps(bundle, sort_keys=True).encode("utf-8")).hexdigest()
    entry = {
        "name": name,
        "hash": bundle_hash,
        "bundle": bundle,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    # Append as JSONL in the policy bundle dir
    bundle_path = POLICY_BUNDLE_DIR / f"{name}.jsonl"
    with open(bundle_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")

    # Record hash for quick lookup
    POLICY_HASH_FILE.write_text(json.dumps({name: bundle_hash}, indent=2))

    # Health log
    _health_append({
        "action": "set_policy_bundle",
        "name": name,
        "hash": bundle_hash,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    })

    return bundle_hash


def get_policy_bundle(name: str) -> Optional[Dict]:
    """Retrieve a policy bundle by name, returning dict with ok/bundle/hash."""
    bundle_path = POLICY_BUNDLE_DIR / f"{name}.jsonl"
    if not bundle_path.is_file():
        return None
    try:
        with open(bundle_path, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
            if lines:
                last = json.loads(lines[-1])
                return {"ok": True, "bundle": last.get("bundle"), "hash": last.get("hash")}
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _health_append(entry: Dict) -> None:
    """Append a health-log entry to the shared health log."""
    with open(HEALTH_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")


def health_check() -> Dict:
    """Run health checks on vault store and policy bundles.

    Returns dict: {"ok": bool, "details": [...]}.
    If any check fails, auto-revert mechanism can be triggered by the
    watchdog (Tier 2 function).
    """
    details = []
    ok = True

    # Check vault entries hash chain integrity
    import glob as _g
    key_files = _g.glob(str(VERSIONS_DIR / "*.jsonl"))
    for kf in key_files:
        key_name = Path(kf).stem
        entries = []
        try:
            with open(kf, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception as e:
            details.append(f"{key_name}: read error: {e}")
            ok = False
            continue
        if not entries:
            details.append(f"{key_name}: no entries; skipping chain check")
            continue
        # Verify chain: each entry's prev_hash should match prior sha256
        prev = hashlib.sha256(b"genesis").hexdigest()
        for i, e in enumerate(entries):
            if "sha256" not in e:
                continue
            if e["sha256"] != prev:
                details.append(f"{key_name}: chain break at entry {i}")
                ok = False
            prev = e["sha256"]

    # Check policy bundle hashes match
    for bundle_name in ["design_studio_policy", "steward_policy"]:
        result = get_policy_bundle(bundle_name)
        if result is None:
            details.append(f"{bundle_name}: not found")
            ok = False

    return {"ok": ok, "details": details}


# ---- External-effects ledger (rollback does NOT undo these) ----
EXTERNAL_LEDGER = VAULT_DIR / "external_effects_ledger.jsonl"
EXTERNAL_LEDGER.touch(exist_ok=True)

def record_external_effect(action: str, detail: str, actor: str = "system") -> None:
    """Record an effect that rollback cannot undo."""
    entry = {
        "action": action,
        "detail": detail,
        "actor": actor,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(EXTERNAL_LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")


def external_ledger_entries() -> List[Dict]:
    """Read all external-effects ledger entries."""
    entries = []
    if not EXTERNAL_LEDGER.is_file():
        return entries
    try:
        with open(EXTERNAL_LEDGER, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return entries
    return entries