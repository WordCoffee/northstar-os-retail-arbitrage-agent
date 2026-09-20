"""Northstar OS Authentication — JWT-based multi-tenant auth.

Provides user registration, login, token refresh, and plan enforcement.
Uses bcrypt for password hashing and PyJWT for token management.

Token structure:
{
    "sub": "<user_id>",
    "email": "<email>",
    "plan": "foundation|scout|mover|autothink",
    "iat": <issued_at>,
    "exp": <expires_at>
}
"""

import os
import json
import time
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import bcrypt
import jwt

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JWT_SECRET = os.environ.get("NORTHSTAR_JWT_SECRET") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Plan entitlements — thin loader over the canonical catalog.
# Single source of truth: shared/subscription-plans.json (A2 migration).
# The PLAN_ENTITLEMENTS variable name and shape are preserved so every
# downstream consumer (main.py routes, auth.register_user, user_has_entitlement,
# get_plan_info) keeps working unchanged: {plan_id: {name, price, gates, description}}.

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLAN_CATALOG_PATH = os.path.join(_REPO_ROOT, "shared", "subscription-plans.json")


def _load_plan_catalog() -> Dict[str, Dict[str, Any]]:
    """Read shared/subscription-plans.json and project it into the legacy shape.

    Fail-closed: a missing/malformed catalog or a plan missing its id raises
    at import so a bad catalog can never silently degrade entitlements.
    """
    try:
        with open(_PLAN_CATALOG_PATH, "r", encoding="utf-8-sig") as _fh:
            catalog = json.load(_fh)
    except (OSError, ValueError) as _exc:
        raise ValueError(
            "Cannot load plan catalog %s: %s" % (_PLAN_CATALOG_PATH, _exc)
        ) from _exc

    if catalog.get("gates_always_off") is not True:
        raise ValueError("Plan catalog invariant breach: gates_always_off must be true")

    plans: Dict[str, Dict[str, Any]] = {}
    for p in catalog.get("plans", []):
        pid = p.get("id")
        if not pid:
            raise ValueError("Plan catalog holds a plan without an id")
        plans[pid] = {
            "name": p["name"],
            "price": p.get("price_usd_month", 0),
            "gates": list(p.get("entitled_gates", [])),
            "description": p.get("description", ""),
        }
    if not plans:
        raise ValueError("Plan catalog holds no plans")
    return plans


PLAN_ENTITLEMENTS = _load_plan_catalog()

# ---------------------------------------------------------------------------
# B2: roles, tenancy, and least-privilege admin (contract: auth-rbac/v1)
# ---------------------------------------------------------------------------
# Role = what a principal may DO within their tenant. Plan = what the tenant is
# ENTITLED to. Effective capability = role permission ∩ plan entitlement.
# Unknown roles fail closed (rank -1 => every role check fails).

ROLE_MEMBER = "member"
ROLE_OPERATOR = "operator"
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"

# Tenant role hierarchy (admin is a SEPARATE axis, deliberately not ranked here,
# so an admin does NOT satisfy owner/operator tenant checks — least privilege).
ROLE_ORDER: Dict[str, int] = {ROLE_MEMBER: 0, ROLE_OPERATOR: 1, ROLE_OWNER: 2}
VALID_ROLES = frozenset(ROLE_ORDER) | {ROLE_ADMIN}

# Plan entitlement order (from the catalog); never duplicated as names/prices.
PLAN_ORDER: Dict[str, int] = {"foundation": 0, "scout": 1, "mover": 2, "autothink": 3}

# Basic account fields an admin may see — nothing security-sensitive.
_ADMIN_ACCOUNT_FIELDS = ("id", "email", "plan", "created_at")


def is_valid_role(role: Any) -> bool:
    return role in VALID_ROLES


def role_rank(role: Any) -> int:
    """Tenant-role rank; unknown roles and the admin axis return -1 (fail closed)."""
    return ROLE_ORDER.get(role, -1)


def plan_rank(plan: Any) -> int:
    return PLAN_ORDER.get(plan, -1)


def is_admin(user: Optional[Dict[str, Any]]) -> bool:
    return bool(user) and user.get("role") == ROLE_ADMIN


def has_role(user: Optional[Dict[str, Any]], minimum_role: str) -> bool:
    """True only when the user's tenant role meets the minimum. Fail closed:
    an unknown minimum_role or an unknown user role returns False; admin does
    not pass tenant-role checks."""
    if minimum_role not in ROLE_ORDER:
        return False
    return role_rank((user or {}).get("role")) >= ROLE_ORDER[minimum_role]


def tenant_id_of(user: Optional[Dict[str, Any]]) -> Optional[str]:
    """Single-tenant-per-account: tenant_id falls back to the account id.
    Fails closed (None) when neither is present."""
    if not user:
        return None
    return user.get("tenant_id") or user.get("id") or None


def admin_account_view(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Least-privilege admin view: ONLY basic account fields. Password hashes,
    tokens, session ids, gate/live state, and tenant product data are
    structurally excluded (contract: security-boundaries/v1 §3)."""
    if not user:
        return {}
    return {k: user.get(k) for k in _ADMIN_ACCOUNT_FIELDS}

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    email: str,
    plan: str = "foundation",
    expires_delta: Optional[timedelta] = None,
    *,
    role: str = ROLE_OWNER,
    tenant_id: Optional[str] = None,
) -> str:
    """Create a JWT access token.

    B2 additive claims: ``role`` (fail-closed to ``member`` on an unknown value)
    and ``tenant_id`` (single-tenant-per-account: defaults to the account id).
    A ``jti`` opaque session id is included. Defaults preserve prior behavior.
    """
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    safe_role = role if role in VALID_ROLES else ROLE_MEMBER
    payload = {
        "sub": user_id,
        "email": email,
        "plan": plan,
        "role": safe_role,
        "tenant_id": tenant_id or user_id,
        "type": "access",
        "jti": "sess_" + secrets.token_hex(16),
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token. Returns payload or raises."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# User store (SQLite-backed for MVP, PostgreSQL in production)
# ---------------------------------------------------------------------------

def _db():
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_layer import get_db
    return get_db()


def _ensure_user_table():
    """Create users table if it doesn't exist."""
    db = _db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT DEFAULT 'foundation',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            last_login_at TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    db.commit()


def register_user(email: str, password: str, plan: str = "foundation") -> Dict[str, Any]:
    """Register a new user. Returns user dict or error."""
    _ensure_user_table()
    db = _db()

    # Validate
    if not email or "@" not in email:
        return {"error": "Invalid email address"}
    if len(password) < 8:
        return {"error": "Password must be at least 8 characters"}
    if plan not in PLAN_ENTITLEMENTS:
        return {"error": f"Invalid plan: {plan}"}

    # Check duplicate
    cur = db.execute("SELECT id FROM users WHERE email = ?", (email.lower().strip(),))
    if cur.fetchone():
        return {"error": "Email already registered"}

    # Create
    user_id = hashlib.sha256(email.lower().strip().encode()).hexdigest()[:16]
    password_hash = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        "INSERT INTO users (id, email, password_hash, plan, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, email.lower().strip(), password_hash, plan, now, now),
    )
    db.commit()

    return {
        "id": user_id,
        "email": email.lower().strip(),
        "plan": plan,
        "created_at": now,
    }


def login_user(email: str, password: str) -> Dict[str, Any]:
    """Authenticate a user and return tokens."""
    _ensure_user_table()
    db = _db()

    cur = db.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email.lower().strip(),))
    user = cur.fetchone()
    if not user:
        return {"error": "Invalid email or password"}

    user = dict(user)
    if not verify_password(password, user["password_hash"]):
        return {"error": "Invalid email or password"}

    # Update last login
    now = datetime.now(timezone.utc).isoformat()
    db.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, user["id"]))
    db.commit()

    access_token = create_access_token(user["id"], user["email"], user["plan"])
    refresh_token = create_refresh_token(user["id"])

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "plan": user["plan"],
        },
    }


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Create a new access token from a refresh token."""
    try:
        payload = decode_token(refresh_token)
    except jwt.ExpiredSignatureError:
        return {"error": "Refresh token expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid refresh token"}

    if payload.get("type") != "refresh":
        return {"error": "Not a refresh token"}

    user_id = payload["sub"]
    db = _db()
    cur = db.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,))
    user = cur.fetchone()
    if not user:
        return {"error": "User not found"}

    user = dict(user)
    access_token = create_access_token(user["id"], user["email"], user["plan"])
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    _ensure_user_table()
    db = _db()
    cur = db.execute("SELECT id, email, plan, created_at, last_login_at FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def update_user_plan(user_id: str, plan: str) -> Dict[str, Any]:
    """Update a user's subscription plan."""
    if plan not in PLAN_ENTITLEMENTS:
        return {"error": f"Invalid plan: {plan}"}
    db = _db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute("UPDATE users SET plan = ?, updated_at = ? WHERE id = ?", (plan, now, user_id))
    db.commit()
    return {"user_id": user_id, "plan": plan, "updated_at": now}


# ---------------------------------------------------------------------------
# Plan enforcement
# ---------------------------------------------------------------------------

def user_has_entitlement(user_id: str, gate: str) -> bool:
    """Check if a user's plan includes a specific capability gate."""
    user = get_user(user_id)
    if not user:
        return False
    plan = user.get("plan", "foundation")
    entitlements = PLAN_ENTITLEMENTS.get(plan, {})
    return gate in entitlements.get("gates", [])


def get_plan_info(plan: str) -> Dict[str, Any]:
    """Get plan details including entitlements."""
    return PLAN_ENTITLEMENTS.get(plan, PLAN_ENTITLEMENTS["foundation"])
