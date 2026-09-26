#!/usr/bin/env python
"""Local production candidate stack runner (1C-LC / Workstream E).

Loopback-only: PostgreSQL (disposable), production-mode auth with temporary
local signing material, backend (uvicorn), worker thread, scheduler thread,
and the canonical React build served at /ui.

Temporary secrets are generated at runtime, never printed or committed, and
cleaned up on shutdown. Usage:

  python -m Northstar_backend.tools.local_production_stack --start
  python -m Northstar_backend.tools.local_production_stack --status
  python -m Northstar_backend.tools.local_production_stack --stop

Requires FOUNDATION_DB_URL (disposable loopback) to be set.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

_STATE_FILE = Path(tempfile.gettempdir()) / "northstar-local-prod-state.json"


def _state():
    if _STATE_FILE.exists():
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _generate_secret() -> str:
    return secrets.token_urlsafe(48)  # >= 32 bytes; never printed


def start(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Start the local production stack")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--org", default="Local Production")
    ap.add_argument("--email", default="owner@local.test")
    args = ap.parse_args(argv)

    db_url = os.environ.get("FOUNDATION_DB_URL")
    if not db_url:
        print("FOUNDATION_DB_URL must be set (disposable loopback PG).")
        return 2
    secret = os.environ.get("NORTHSTAR_JWT_SECRET") or _generate_secret()
    os.environ["ENVIRONMENT"] = "production"
    os.environ["NORTHSTAR_UI_MODE"] = "private_beta"  # legacy Operations Hub hidden locally
    os.environ["NORTHSTAR_JWT_SECRET"] = secret
    os.environ["NORTHSTAR_JWT_ISSUER"] = "https://northstar.local"
    os.environ["NORTHSTAR_JWT_AUDIENCE"] = "northstar-api"
    os.environ["NORTHSTAR_JWT_ALGORITHMS"] = "HS256"
    os.environ["NS_FOUNDATION_BIND_HOST"] = args.host
    os.environ["NORTHSTAR_JWT_KEY_ID"] = "local-prod-kid"
    os.environ["NORTHSTAR_JWT_TOKEN_TYPES"] = "access"

    from Northstar_backend.foundation.local_stack import LocalProductionCandidate
    from Northstar_backend.foundation.authn import (
        validate_auth_configuration, assert_startup_posture,
    )
    problems = validate_auth_configuration("production")
    if problems:
        print("AUTH CONFIGURATION PROBLEMS:", problems)
        return 2
    posture = assert_startup_posture(bind_host=args.host)
    if posture["binds_beyond_loopback"]:
        print("REFUSING: bind is beyond loopback.")
        return 2

    token_path = str(Path(tempfile.gettempdir()) / "northstar-local-prod-token.txt")
    token_nonce = secrets.token_urlsafe(16)
    stack = LocalProductionCandidate(
        db_url=db_url, issuer="https://northstar.local",
        audience="northstar-api", org_name=args.org, user_email=args.email)

    # Apply the canonical additive migrations so a fresh disposable DB has the
    # full schema (001-007) BEFORE the state (which seeds) is built.
    from Northstar_backend.foundation.db_postgres import PostgresFoundationDB
    _pg = PostgresFoundationDB(db_url)
    for _m in ("001_foundation.sql", "002_jobs_durable.sql",
               "003_keyword_intel.sql", "004_financial_integrity.sql",
               "005_beta_launch_controls.sql", "006_private_beta_readiness.sql",
               "007_private_beta_operations.sql"):
        _pg.apply_sql_file(os.path.join("Northstar_backend", "migrations_foundation", _m))
    _pg.close()

    stack.build_state()
    boot = stack.bootstrap_owner(token_path=token_path)

    # Private-beta posture: publish the current legal documents and record the
    # operator's acceptance so the gate is ACTIVE (new testers must accept in
    # the UI). Mirrors the staging posture.
    from Northstar_backend.foundation.beta.acceptance import (
        publish_documents, record_acceptance,
    )
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Role as _Role
    from Northstar_backend.foundation.enums import Environment as _Env
    publish_documents(stack.state)
    boot_ctx = build_context(user_id=boot["user_id"],
                             organization_id=boot["organization_id"],
                             role=_Role.ORGANIZATION_OWNER.value,
                             environment=_Env.PRODUCTION.value)
    record_acceptance(stack.state, boot_ctx, business_use=True, age_18_plus=True,
                      request_id="local-stack-boot")

    stack.start_worker()
    stack.start_scheduler()

    import uvicorn
    from Northstar_backend.foundation.app import create_app
    from fastapi import FastAPI
    app = create_app()

    # Loopback-only convenience for the local browser harness: serves the
    # temporary token at a nonce-guarded URL so the token never appears in
    # logs or the conversation. Not present in the shipped foundation app.
    from fastapi.responses import PlainTextResponse

    @app.get(f"/local-token/{token_nonce}", include_in_schema=False)
    def local_token():
        resp = PlainTextResponse(
            Path(token_path).read_text(encoding="utf-8").strip()
            if Path(token_path).exists() else "", status_code=404
            if not Path(token_path).exists() else 200)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Local platform-admin token (loopback-only dev convenience; not shipped).
    admin_token_file = Path(os.environ.get("LOCALAPPDATA", Path.home())) / \
        "northstar-local-admin-token.txt"

    @app.get("/local-token/admin", include_in_schema=False)
    def local_admin_token():
        body = admin_token_file.read_text(encoding="utf-8").strip() \
            if admin_token_file.exists() else ""
        resp = PlainTextResponse(body, status_code=404 if not body else 200)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    tester_token_file = Path(os.environ.get("LOCALAPPDATA", Path.home())) / \
        "northstar-local-tester-token.txt"

    @app.get("/local-token/tester", include_in_schema=False)
    def local_tester_token():
        body = tester_token_file.read_text(encoding="utf-8").strip() \
            if tester_token_file.exists() else ""
        resp = PlainTextResponse(body, status_code=404 if not body else 200)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Loopback-only one-click local login: stores the dev token into the
    # browser's ns-access-token key, then lands on the right beta screen.
    from fastapi.responses import HTMLResponse

    @app.get("/local-login/{which}", include_in_schema=False)
    def local_login(which: str):
        kind = "admin" if which in ("admin", "local-admin") else "tester"
        target = "#/beta-ops" if kind == "admin" else "#/beta"
        body = f"""<!doctype html><meta charset="utf-8"><title>Local login</title>
<script>
  fetch('/local-token/{kind}', {{ cache: 'no-store' }})
    .then(r => r.ok ? r.text() : Promise.reject('no token'))
    .then(t => {{ localStorage.setItem('ns-access-token', t.trim()); location.href = '/ui{target}'; }})
    .catch(() => document.body.append('No local token — mint one first.'));
</script>
Signing you in locally…"""
        resp = HTMLResponse(body)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    _STATE_FILE.write_text(json.dumps({
        "pid": os.getpid(), "host": args.host, "port": args.port,
        "org": boot["organization_id"], "user": boot["user_id"],
        "issuer": "https://northstar.local", "audience": "northstar-api",
        "token_path": token_path, "token_url": f"/local-token/{token_nonce}",
        "db_url": _redact(db_url),
        "started_at": time.time(),
    }, indent=2), encoding="utf-8")

    print(f"Local production stack starting on http://{args.host}:{args.port}/ui "
          f"(loopback only). Ctrl+C to stop.")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        stop_cleanup(stack, token_path)
    return 0


def _redact(url: str) -> str:
    from urllib.parse import urlparse
    u = urlparse(url)
    return f"postgresql://{u.username}@127.0.0.1:{u.port}/{u.path.lstrip('/')}"


def stop_cleanup(stack=None, token_path: Optional[str] = None) -> None:
    if stack is not None:
        stack.stop()
    if token_path and os.path.exists(token_path):
        try:
            os.unlink(token_path)  # temp token cleaned up
        except OSError:
            pass
    if _STATE_FILE.exists():
        try:
            _STATE_FILE.unlink()
        except OSError:
            pass


def status(argv=None) -> int:
    s = _state()
    if not s:
        print("Local production stack: not running.")
        return 0
    print(json.dumps(s, indent=2))
    return 0


def stop(argv=None) -> int:
    s = _state()
    if not s:
        print("Local production stack: not running.")
        return 0
    # The stack runs in-process; terminating this CLI is the stop signal.
    # We clean the state/token regardless.
    stop_cleanup()
    print("Local production stack stopped; temporary secrets cleaned up.")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] == "start":
        return start(args[1:])
    if args[0] == "status":
        return status(args[1:])
    if args[0] == "stop":
        return stop(args[1:])
    print("usage: local_production_stack {start|status|stop} [--port N]")
    return 2


if __name__ == "__main__":
    sys.exit(main())