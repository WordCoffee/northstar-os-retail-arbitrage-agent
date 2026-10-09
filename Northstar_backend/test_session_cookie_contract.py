"""Regression tests for the two session bugs found while standing up the
local operator sign-in (2026-10-09).

1. The session cookie was scoped to ``path=/api/v1/foundation``, so a signed-in
   browser never sent it to ``/api/autothink/*`` — a valid session got a 401
   from one API prefix and a 200 from another.
2. ``require_session`` resolved the HttpOnly cookie against the legacy
   ``auth.py`` SQLite user table instead of the Foundation store that actually
   minted it, and it verified the JWT's issuer/audience via the ``options``
   dict (which PyJWT ignores) while leaving ``verify_aud`` at its default.

Both tests are hermetic: a real token is minted with the real signer, and the
Foundation store is built against a temp database.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import foundation.auth_session as auth_session  # noqa: E402


class SessionCookieScopeTests(unittest.TestCase):
    """The cookie path must cover every API prefix, not just Foundation."""

    def test_session_cookie_path_is_root(self):
        self.assertEqual(auth_session.SESSION_PATH, "/",
                         "the session cookie must be sent to every /api prefix")

    def test_session_cookie_path_is_not_foundation_only(self):
        self.assertNotEqual(auth_session.SESSION_PATH, "/api/v1/foundation")

    def test_cookie_kwargs_use_the_root_path(self):
        kwargs = auth_session.session_cookie_kwargs("value", max_age=60)
        self.assertEqual(kwargs["path"], "/")
        self.assertTrue(kwargs["httponly"])

    def test_session_cookie_covers_the_autothink_prefix(self):
        """The exact regression: /api/autothink must be inside the cookie path."""
        path = auth_session.SESSION_PATH
        self.assertTrue(path == "/" or "/api/autothink".startswith(path))


class FoundationCookieResolutionTests(unittest.TestCase):
    """A valid Foundation cookie resolves to a tenant-scoped user."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="ns-cookie-resolve-")
        self._secret = "unit-test-signing-key-not-a-real-secret-value"
        self._env = patch.dict(os.environ, {
            "NORTHSTAR_JWT_SECRET": self._secret,
            "NORTHSTAR_JWT_ISSUER": "https://northstar.local",
            "NORTHSTAR_JWT_AUDIENCE": "northstar-api",
        }, clear=False)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def _build_state(self):
        from foundation.api.state import FoundationState
        return FoundationState.build(os.path.join(self._tmp, "foundation.db"))

    def _make_session(self, state, user_id, org_id, role="organization_owner",
                      register=True):
        """Mint a token exactly the way the login route does.

        ``register`` mirrors ``state.repos.sessions.register(jti, ...)`` in the
        login handler, so a token without it stands for 'never logged in'.
        """
        token, jti, exp = auth_session.mint_access_token(
            user_id=user_id, org_id=org_id, role=role)
        if register:
            state.repos.sessions.register(jti, user_id, org_id, exp.isoformat())
        return token, jti, exp

    def _resolve(self, token, state):
        from auth_deps import _resolve_foundation_cookie
        return _resolve_foundation_cookie(token, state=state)

    def _make_owner(self, state, slug, email, password="correct-horse-battery"):
        """Bootstrap an idempotent owner and guarantee a credential exists."""
        from foundation.bootstrap import bootstrap_owner
        from foundation import credentials

        credentials.ensure_table(state.db)
        try:
            result = bootstrap_owner(state, org_name=slug.replace("-", " ").title(),
                                     user_email=email, org_slug=slug)
        except Exception:
            result = bootstrap_owner(state, org_name=slug.replace("-", " ").title(),
                                     user_email=email, org_slug=slug, recover=True)
        if credentials.get_by_email(state.db, email) is None:
            credentials.create(state.db, user_id=result["user_id"],
                               email=email, password=password)
        return result

    def test_a_valid_cookie_resolves_with_tenant_and_role(self):
        state = self._build_state()
        try:
            email = "cookie-test@northstar.test"
            result = self._make_owner(state, "cookie-org", email)
            token, _jti, _exp = self._make_session(
                state, result["user_id"], result["organization_id"])
        finally:
            pass

        user = self._resolve(token, state)
        state.close()
        self.assertIsNotNone(user, "a valid Foundation cookie must resolve")
        self.assertEqual(user["tenant_id"], result["organization_id"])
        self.assertEqual(user["role"], "organization_owner")
        self.assertEqual(user["id"], result["user_id"])

    def test_a_revoked_cookie_is_refused(self):
        state = self._build_state()
        try:
            email = "revoked-test@northstar.test"
            result = self._make_owner(state, "revoked-org", email)
            token, jti, _exp = self._make_session(
                state, result["user_id"], result["organization_id"])
            state.repos.sessions.revoke(jti, reason="logout")
        finally:
            pass

        self.assertIsNone(self._resolve(token, state),
                          "a logged-out session must stop working immediately")
        state.close()

    def test_a_token_that_was_never_registered_is_refused(self):
        """Fail closed: no session row means it never went through login."""
        state = self._build_state()
        try:
            email = "unregistered-test@northstar.test"
            result = self._make_owner(state, "unregistered-org", email)
            token, _jti, _exp = self._make_session(
                state, result["user_id"], result["organization_id"],
                register=False)
        finally:
            pass

        self.assertIsNone(self._resolve(token, state))
        state.close()

    def test_a_garbage_cookie_is_refused(self):
        self.assertIsNone(self._resolve("not-a-jwt", None))
        self.assertIsNone(self._resolve("", None))

    def test_a_token_without_an_organization_is_refused(self):
        """No resolved org is refused, never scoped to a shared bucket."""
        state = self._build_state()
        try:
            email = "noorg-test@northstar.test"
            result = self._make_owner(state, "no-org", email)
            token, _jti, _exp = self._make_session(
                state, result["user_id"], None, role=None)
        finally:
            pass

        self.assertIsNone(self._resolve(token, state))
        state.close()


if __name__ == "__main__":
    unittest.main()
