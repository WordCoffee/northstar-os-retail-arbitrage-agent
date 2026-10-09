"""JWT signing-key posture tests.

An ephemeral secret is acceptable in dev/test (it invalidates nothing real)
and REFUSED in hosted mode, where it would silently log everyone out on every
restart. The secret VALUE is never inspected, printed, or asserted.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402


def test_dev_ephemeral_secret_is_allowed():
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        with patch.object(auth, "JWT_SECRET_IS_EPHEMERAL", True):
            auth.assert_jwt_secret_posture()  # must not raise


def test_unset_environment_ephemeral_secret_is_allowed():
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(auth, "JWT_SECRET_IS_EPHEMERAL", True):
            auth.assert_jwt_secret_posture()  # must not raise


def test_hosted_ephemeral_secret_is_refused():
    for environment in ("staging", "production"):
        with patch.dict(os.environ, {"ENVIRONMENT": environment}, clear=False):
            with patch.object(auth, "JWT_SECRET_IS_EPHEMERAL", True):
                problems = auth.jwt_secret_posture_problems()
                assert problems, environment
                assert "NORTHSTAR_JWT_SECRET" in problems[0]
                try:
                    auth.assert_jwt_secret_posture()
                except RuntimeError as exc:
                    assert "JWT SECRET POSTURE VIOLATION" in str(exc)
                else:  # pragma: no cover - defensive
                    raise AssertionError("hosted ephemeral secret was allowed")


def test_hosted_persistent_secret_is_allowed():
    with patch.object(auth, "JWT_SECRET_IS_EPHEMERAL", False):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            assert auth.jwt_secret_posture_problems() == []
            auth.assert_jwt_secret_posture()  # must not raise
