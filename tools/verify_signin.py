"""Prove the local sign-in works, without ever printing the password.

Signs in through the REAL route the SPA uses (/api/v1/foundation/auth/login),
holds the session cookie, and then checks /me, the CSRF guard, and the
authenticated AutothinK surface (P0-04). Prints only statuses and a masked
identity.
"""
import os
import sys
import urllib.request
import urllib.error
import http.cookiejar
import json

BASE = os.environ.get("HARNESS_BASE_URL", "http://127.0.0.1:80")
EMAIL = os.environ.get("NS_OWNER_EMAIL", "t2").strip().lower()
PASSWORD = os.environ.get("NS_OWNER_PASSWORD", "")

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None, headers=None, expect_json=True):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = opener.open(req, timeout=20)
        raw = resp.read().decode("utf-8", "replace")
        code = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        code = exc.code
    parsed = None
    if expect_json and raw:
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
    return code, parsed, raw


def masked(email):
    if "@" not in email:
        return email[:1] + "***"
    local, domain = email.split("@", 1)
    return local[:1] + "***@" + domain


def main() -> int:
    ok = True

    print("1. GET /health")
    code, body, _ = call("GET", "/health")
    print(f"   -> {code} {body if body else ''}")
    ok &= code == 200

    print("2. POST /api/v1/foundation/auth/login (real route, real credentials)")
    code, body, raw = call("POST", "/api/v1/foundation/auth/login",
                           {"email": EMAIL, "password": PASSWORD})
    print(f"   -> {code}")
    if code != 200:
        print(f"   FAILED: {raw[:300]}")
        return 1
    cookies = sorted(c.name for c in jar)
    print(f"   session cookies: {cookies}")
    ok &= "ns_session" in cookies
    ok &= "ns_csrf" in cookies
    leaked = any(c.value.startswith("eyJ") for c in jar if c.name != "ns_session")
    print(f"   token leaked to a JS-readable cookie: {leaked}")

    print("3. GET /api/v1/foundation/me")
    code, body, _ = call("GET", "/api/v1/foundation/me")
    print(f"   -> {code} user_id={(body or {}).get('user_id')} "
          f"role={(body or {}).get('role')} "
          f"org={(body or {}).get('organization_id')}")
    ok &= code == 200

    print("4. GET /api/autothink/history (P0-04: authenticated + tenant-scoped)")
    code, body, _ = call("GET", "/api/autothink/history?limit=3")
    print(f"   -> {code} total={(body or {}).get('total')} "
          f"org={(body or {}).get('org_id')}")
    ok &= code == 200

    print("5. GET /api/autothink/usage")
    code, body, _ = call("GET", "/api/autothink/usage")
    print(f"   -> {code} runs={(body or {}).get('runs')} "
          f"cost={(body or {}).get('cost_usd_recorded')}")
    ok &= code == 200

    print("6. POST /api/v1/foundation/auth/logout WITHOUT a CSRF header -> 403")
    code, _, _ = call("POST", "/api/v1/foundation/auth/logout")
    print(f"   -> {code}")
    ok &= code == 403

    csrf = next((c.value for c in jar if c.name == "ns_csrf"), None)
    print("7. POST /api/v1/foundation/auth/logout WITH the CSRF header -> 200")
    code, _, _ = call("POST", "/api/v1/foundation/auth/logout",
                      headers={"X-CSRF-Token": csrf} if csrf else {})
    print(f"   -> {code}")
    ok &= code == 200

    print("8. GET /api/v1/foundation/me after logout -> 401")
    code, _, _ = call("GET", "/api/v1/foundation/me")
    print(f"   -> {code}")
    ok &= code == 401

    print("9. sign in again so the operator has a live session file")
    code, _, _ = call("POST", "/api/v1/foundation/auth/login",
                      {"email": EMAIL, "password": PASSWORD})
    print(f"   -> {code}")
    ok &= code == 200

    print()
    print(f"account: {masked(EMAIL)} (password not printed)")
    print(f"sign-in URL: {BASE}/ui/sign-in")
    print()
    print("RESULT: " + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
