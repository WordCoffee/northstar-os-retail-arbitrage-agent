"""Master Brain Profile Loader — resolve the active subscriber and load their profile.

Offline, additive-only. No LLM calls, no network calls, no credentials.

This is the session-start bootstrap of the Master Brain, paired with
`master_brain_gateway.py` (deterministic task classifier + append-only audit log):

    1. resolve_active_profile()  -> WHO is asking?  (identity --> profile id)
    2. load_profile(profile_id)  -> WHAT does the brain know about them?
    3. audit_profile_load()      -> append-only record of the profile load

Identity resolution is a PLUGGABLE, priority-ordered resolver chain. Today only
the local-default resolver is active (env `NORTHSTAR_PROFILE` or the manifest
default). Future identity sources — login session tokens, IP address geolocation,
two-step (2FA) verification — register via `register_resolver()` and are tried in
priority order; unregistered/stub resolvers are skipped without failing the chain.

The canonical index of who exists lives in `master-brain/profiles/manifest.json`.
Unknown or unlisted profile ids fail closed (they are never fabricated).
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Project-root canonical paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(REPO_ROOT, "master-brain", "profiles")
MANIFEST_PATH = os.path.join(PROFILES_DIR, "manifest.json")

# Environment variable an operator may set to force a specific profile
# (non-secret config flag — the profile id is a public name, never a credential).
ENV_PROFILE = "NORTHSTAR_PROFILE"

# Stable fallback used while T2 is the only subscriber (the "master seed").
DEFAULT_PROFILE = "t2-holdings-tyrone-johnson"

# Audit track reused from the gateway taxonomy (platform/admin access layer).
AUDIT_TRACK = "PLATFORM_ADMIN"

_PROFILE_PATH_CACHE: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Identity resolvers (pluggable chain, highest priority first)
# ---------------------------------------------------------------------------

class IdentityResolver:
    """Base class for identity --> profile resolution.

    `priority` orders the chain (highest wins when multiple *match*).
    `resolve()` returns a profile id string, or None if this source cannot
    identify the caller (fall through to the next resolver).
    """

    name = "base"
    priority = 0

    def resolve(self, identity: Optional[str] = None) -> Optional[str]:
        raise NotImplementedError


class LocalDefaultResolver(IdentityResolver):
    """Local bootstrap: env override or the manifest default profile.

    Active TODAY. Not an authentication source — it is the single-tenant
    bootstrap that makes the brain usable before login/IP/2FA exist.
    """

    name = "local_default"
    priority = 10

    def resolve(self, identity: Optional[str] = None) -> Optional[str]:
        forced = os.environ.get(ENV_PROFILE, "").strip()
        if forced:
            return forced
        try:
            manifest = load_manifest()
        except (OSError, ValueError, json.JSONDecodeError):
            return DEFAULT_PROFILE
        return manifest.get("default_profile") or DEFAULT_PROFILE


class LoginSessionResolver(IdentityResolver):
    """FUTURE: login session token --> subscriber profile.

    NOT IMPLEMENTED. Registered today so the chain, priority, and tests already
    exercise the plug-in slot without any live auth dependency.
    """

    name = "login_session"
    priority = 100

    def resolve(self, identity: Optional[str] = None) -> Optional[str]:
        # TODO(future): map verified login/session credentials to a subscriber id.
        # Returns None (no match) until real session auth is wired.
        return None


class IPAddressResolver(IdentityResolver):
    """FUTURE: IP address geolocation --> subscriber profile.

    NOT IMPLEMENTED. Registered today as the plug-in slot; returns None until
    wired. Never trusts an IP alone for identification once subscribers exist.
    """

    name = "ip_address"
    priority = 90

    def resolve(self, identity: Optional[str] = None) -> Optional[str]:
        # TODO(future): IP is a weak signal (shared NAT/proxies) — always combine
        # with a stronger factor (login or 2FA) before returning a profile.
        return None


class TwoStepAuthResolver(IdentityResolver):
    """FUTURE: two-step (2FA) verification --> subscriber profile.

    NOT IMPLEMENTED. Registered today as the plug-in slot; returns None until
    wired. The strongest factor — the primary confirmation the operator named.
    """

    name = "two_step_auth"
    priority = 200

    def resolve(self, identity: Optional[str] = None) -> Optional[str]:
        # TODO(future): verification challenge (TOTP/authenticator/passkey) has
        # succeeded for a known subscriber id -> return that id.
        return None


# Priority-ordered registry. Lower index = tried first (higher priority).
_RESOLVERS: List[IdentityResolver] = [
    TwoStepAuthResolver(),   # strongest factor first (future)
    LoginSessionResolver(),  # session factor second (future)
    IPAddressResolver(),     # weak factor third (future, combine with above)
    LocalDefaultResolver(),  # bootstrap fallback (active today)
]


def register_resolver(resolver: IdentityResolver) -> None:
    """Add an identity resolver to the chain (sorted by priority, desc)."""
    _RESOLVERS.append(resolver)
    _RESOLVERS.sort(key=lambda r: -r.priority)


# ---------------------------------------------------------------------------
# Manifest (canonical index of subscriber profiles)
# ---------------------------------------------------------------------------

def load_manifest(manifest_path: Optional[str] = None) -> Dict:
    """Read and validate the profile manifest (canonical profile index)."""
    path = manifest_path or MANIFEST_PATH
    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    if not isinstance(manifest, dict) or "profiles" not in manifest:
        raise ValueError(f"manifest {path} missing 'profiles' array")
    if not isinstance(manifest["profiles"], list):
        raise ValueError(f"manifest {path} 'profiles' must be an array")
    return manifest


def list_profiles(manifest_path: Optional[str] = None) -> List[str]:
    """Return canonical profile ids (in manifest order)."""
    manifest = load_manifest(manifest_path)
    return [p.get("id") for p in manifest.get("profiles", []) if isinstance(p, dict) and p.get("id")]


def _manifest_entry(profile_id: str, manifest: Dict) -> Dict:
    for p in manifest.get("profiles", []):
        if isinstance(p, dict) and p.get("id") == profile_id:
            return p
    raise KeyError(profile_id)


# ---------------------------------------------------------------------------
# Profile path resolution (fail-closed: never fabricate, block traversal)
# ---------------------------------------------------------------------------

def profile_path(profile_id: str, manifest_path: Optional[str] = None) -> str:
    """Resolve a profile id to its absolute markdown path.

    Raises KeyError if the id is not in the manifest (canonical index).
    Raises ValueError on path traversal outside PROFILES_DIR.
    """
    cache_key = (manifest_path or MANIFEST_PATH, profile_id)
    if cache_key in _PROFILE_PATH_CACHE:
        return _PROFILE_PATH_CACHE[cache_key]

    manifest = load_manifest(manifest_path)
    entry = _manifest_entry(profile_id, manifest)
    file_name = entry.get("file")
    if not file_name:
        raise ValueError(f"manifest entry for '{profile_id}' missing 'file'")

    dir_root = os.path.dirname(manifest_path) if manifest_path else PROFILES_DIR
    candidate = os.path.abspath(os.path.join(dir_root, file_name))
    root = os.path.abspath(dir_root)
    if not candidate.startswith(root + os.sep):
        raise ValueError(f"profile file escapes profiles dir: {candidate}")
    if not file_name.endswith(".md"):
        raise ValueError(f"profile file must be markdown: {file_name}")
    if not os.path.isfile(candidate):
        raise ValueError(f"profile file missing on disk: {candidate}")

    _PROFILE_PATH_CACHE[cache_key] = candidate
    return candidate


# ---------------------------------------------------------------------------
# Resolution + loading
# ---------------------------------------------------------------------------

def resolve_active_profile(identity: Optional[str] = None) -> Dict:
    """Determine the active subscriber profile id via the resolver chain.

    Returns a dict: {profile_id, resolver, resolvers_skipped, warnings}.
    Always resolves to SOMETHING (single-tenant bootstrap defaults to T2) but
    the resolver that matched is always reported for auditability.
    """
    skipped = []
    for resolver in _RESOLVERS:
        try:
            pid = resolver.resolve(identity)
        except NotImplementedError:
            skipped.append(resolver.name)
            continue
        except Exception as exc:  # noqa: BLE001 - a broken resolver must not kill bootstrap
            skipped.append(f"{resolver.name}({type(exc).__name__})")
            continue
        if pid and isinstance(pid, str) and pid.strip():
            return {
                "profile_id": pid.strip(),
                "resolver": resolver.name,
                "resolvers_skipped": skipped,
                "warnings": [],
            }
        skipped.append(resolver.name)

    # Fail-closed single-tenant fallback: T2 master seed is the only profile.
    return {
        "profile_id": DEFAULT_PROFILE,
        "resolver": "local_default",
        "resolvers_skipped": skipped,
        "warnings": ["no identity source matched; used local-default bootstrap"],
    }


def load_profile(profile_id: str, identity: Optional[str] = None,
                 manifest_path: Optional[str] = None,
                 include_content: bool = False) -> Dict:
    """Load a profile: validate existence + integrity, return metadata.

    Returns a dict with profile_id, profile_path, size_bytes, sha256, and a
    short head preview. Raises KeyError/ValueError for unknown/invalid ids —
    the caller must never fabricate a profile.
    """
    path = profile_path(profile_id, manifest_path=manifest_path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    lines = content.splitlines()
    head = lines[:8]

    result = {
        "profile_id": profile_id,
        "profile_path": path,
        "exists": True,
        "size_bytes": len(content.encode("utf-8")),
        "line_count": len(lines),
        "sha256": digest,
        "loaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "head": head,
    }
    if include_content:
        result["content"] = content
    return result


def audit_profile_load(profile_id: str, resolver: str = "local_default",
                       log_path: Optional[str] = None) -> str:
    """Append a profile-load audit entry (append-only, via the gateway).

    Returns the path written to. Never contains credentials.
    """
    try:
        import master_brain_gateway as mbg  # local import keeps option clean
    except ImportError:
        # Gateway lives next to this module in Northstar_backend; if it is
        # unavailable the audit is best-effort and reported as such.
        raise RuntimeError("master_brain_gateway.py not importable; cannot audit")

    # Record the real profile file path (relative to repo root) in files_touched.
    try:
        p_path = profile_path(profile_id)
        touched = [os.path.relpath(p_path, start=REPO_ROOT)]
    except (KeyError, ValueError, OSError):
        touched = [f"profiles/{profile_id}"]  # unresolved id — still auditable

    return mbg.write_audit_entry(
        track=AUDIT_TRACK,
        files_touched=touched,
        live_action_requested=False,
        approval_status="not_requested",
        metadata={"event": "profile_load", "profile_id": profile_id, "resolver": resolver},
        log_path=log_path,
    )


def bootstrap(identity: Optional[str] = None,
              manifest_path: Optional[str] = None,
              audit: bool = False) -> Dict:
    """One-call session bootstrap: resolve active profile + load it (+ audit).

    This is what AGENTS.md §0.1 directs every session to invoke first.
    """
    resolved = resolve_active_profile(identity)
    pid = resolved["profile_id"]
    loaded = load_profile(pid, identity=identity, manifest_path=manifest_path)
    ctx = {
        "resolved": resolved,
        "profile": loaded,
        "audit": None,
    }
    if audit:
        ctx["audit"] = audit_profile_load(pid, resolver=resolved["resolver"])
    return ctx


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="master_brain_profiles",
        description="Master Brain profile bootstrap: resolve active subscriber + load profile.",
    )
    parser.add_argument("--list", action="store_true", help="list canonical profile ids from the manifest")
    parser.add_argument("--resolve", action="store_true", help="resolve the active subscriber profile id")
    parser.add_argument("--identity", default=None, help="identity token passed into the resolver chain (future factors)")
    parser.add_argument("--load", metavar="PROFILE_ID", default=None, help="validate + load a specific profile")
    parser.add_argument("--audit", action="store_true", help="append an audit entry for the profile load")
    parser.add_argument("--bootstrap", action="store_true", help="resolve + load + audit in one step (session start)")
    args = parser.parse_args(argv)

    exit_code = 0

    if args.list:
        try:
            ids = list_profiles()
            print(f"profiles ({len(ids)}): {', '.join(ids)}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR listing profiles: {exc}")
            exit_code = 1

    if args.resolve or args.bootstrap:
        try:
            resolved = resolve_active_profile(args.identity)
            print(f"active_profile={resolved['profile_id']} via={resolved['resolver']}")
            if resolved["warnings"]:
                for w in resolved["warnings"]:
                    print(f"  warning: {w}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR resolving profile: {exc}")
            exit_code = 1

    target = args.load
    if args.bootstrap and not target:
        target = resolve_active_profile(args.identity).get("profile_id")

    if target:
        try:
            loaded = load_profile(target)
            print(f"profile={loaded['profile_id']}")
            print(f"  path={loaded['profile_path']}")
            print(f"  size={loaded['size_bytes']} bytes, lines={loaded['line_count']}")
            print(f"  sha256={loaded['sha256']}")
            print(f"  head:")
            for line in loaded["head"]:
                print(f"    | {line}")
            if args.audit or args.bootstrap:
                log = audit_profile_load(target, resolver="cli")
                print(f"  audit_log={log}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR loading profile '{target}': {exc}")
            exit_code = 1
    elif args.audit:
        print("ERROR: --audit requires --load PROFILE_ID or --bootstrap")
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(_cli())