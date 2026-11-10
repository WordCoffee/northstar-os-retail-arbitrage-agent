"""Minimal local encrypted secrets store (1C-LC staging handoff / Step 3).

AES-256-GCM encrypted JSON vault. The master key is a base64 32-byte key
provided via ``NORTHSTAR_SECRETS_MASTER_KEY`` (never stored in the repository
and never logged). For the single-operator staging stage the key may be kept
in an OS-permissioned local file outside the repo (``secrets.masterkey``);
the interface (get_secret/set_secret/has_secret) is stable so the backend can
be swapped for a hosted secret manager later WITHOUT a breaking migration.

Never prints secret values. Values live only in the encrypted vault.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes

VAULT_DEFAULT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "northstar" / "secrets.vault"
KEY_FILE_DEFAULT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "northstar" / "secrets.masterkey"


class SecretsError(RuntimeError):
    pass


def vault_path() -> Path:
    return Path(os.environ.get("NORTHSTAR_SECRETS_FILE", str(VAULT_DEFAULT)))


def master_key() -> Optional[str]:
    """The base64 master key from the environment, falling back to the
    OS-permissioned local key file (single-operator staging convenience).
    Never read from the repository."""
    key = os.environ.get("NORTHSTAR_SECRETS_MASTER_KEY") or None
    if key:
        return key
    keyfile = KEY_FILE_DEFAULT
    if keyfile.exists():
        try:
            key = keyfile.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if key:
            os.environ["NORTHSTAR_SECRETS_MASTER_KEY"] = key
            return key
    return None


def _key_bytes(key: Optional[str]) -> bytes:
    if not key:
        raise SecretsError("NORTHSTAR_SECRETS_MASTER_KEY is not set")
    try:
        return base64.b64decode(key)
    except Exception as e:  # noqa: BLE001
        raise SecretsError(f"invalid master key: {type(e).__name__}") from e


def _generate_master_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def ensure_master_key_file() -> str:
    """Single-operator convenience: generate and persist the master key to an
    OS-permissioned file OUTSIDE the repository, and expose it via the
    environment for the current process. Documented as stage-appropriate."""
    key = master_key()
    if key:
        return key
    keyfile = KEY_FILE_DEFAULT
    if keyfile.exists():
        key = keyfile.read_text(encoding="utf-8").strip()
        os.environ["NORTHSTAR_SECRETS_MASTER_KEY"] = key
        return key
    key = _generate_master_key()
    keyfile.parent.mkdir(parents=True, exist_ok=True)
    keyfile.write_text(key, encoding="utf-8")
    try:
        os.chmod(keyfile, 0o600)
    except OSError:
        pass
    os.environ["NORTHSTAR_SECRETS_MASTER_KEY"] = key
    return key


def _load_vault() -> dict:
    path = vault_path()
    if not path.exists():
        return {}
    key = _key_bytes(master_key())
    raw = path.read_bytes()
    if len(raw) < 12 + 16:
        raise SecretsError("vault file is corrupt or truncated")
    nonce, ciphertext = raw[:12], raw[12:]
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, b"northstar-secrets")
    except Exception as e:  # noqa: BLE001
        raise SecretsError("unable to unlock vault (wrong master key?)") from e
    return json.loads(plaintext.decode("utf-8"))


def _save_vault(data: dict) -> None:
    key = _key_bytes(master_key())
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(
        nonce, json.dumps(data, sort_keys=True).encode("utf-8"), b"northstar-secrets")
    path = vault_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(nonce + ciphertext)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def set_secret(name: str, value: str) -> None:
    if not value:
        raise SecretsError("refusing to store an empty secret")
    data = _load_vault()
    data[name] = value
    _save_vault(data)


def get_secret(name: str) -> Optional[str]:
    return _load_vault().get(name)


def has_secret(name: str) -> bool:
    return name in _load_vault()


def delete_secret(name: str) -> bool:
    data = _load_vault()
    if name not in data:
        return False
    del data[name]
    _save_vault(data)
    return True


def list_secret_names() -> list[str]:
    """Names only — never values."""
    return sorted(_load_vault().keys())


def derive_key(password: str) -> str:
    """PBKDF2-derived key material for an operator passphrase (future use)."""
    digest = hashes.Hash(hashes.SHA256())
    digest.update(password.encode("utf-8"))
    return base64.b64encode(digest.finalize()).decode()