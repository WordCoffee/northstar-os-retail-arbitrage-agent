"""FastAPI authentication dependencies — OAuth2 + JWT integration.

Provides `get_current_user` dependency for protected routes and
`require_plan` factory for plan-gated endpoints.

Usage in main.py:
    from auth_deps import get_current_user, require_plan

    @app.get("/api/v1/products")
    def list_products(user = Depends(get_current_user)):
        ...

    @app.post("/api/v1/listings/generate")
    def gen_listing(user = Depends(require_plan("scout"))):
        ...
"""

import os
import sys
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

sys.path.insert(0, os.path.dirname(__file__))
import auth

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """Validate JWT and return user payload.

    For the demo/launch phase, requests without a token get a
    read-only 'foundation' user so the UI works without auth setup.
    """
    if not token:
        # Demo mode — allow unauthenticated read-only access
        return {
            "id": "anonymous",
            "email": "demo@northstar.local",
            "plan": "foundation",
            "is_demo": True,
        }

    try:
        payload = auth.decode_token(token)
    except auth.jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user = auth.get_user(payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def require_plan(minimum_plan: str):
    """Factory that returns a dependency requiring a minimum subscription plan.

    Plan hierarchy: foundation < scout < mover < autothink
    """
    plan_order = {"foundation": 0, "scout": 1, "mover": 2, "autothink": 3}
    min_level = plan_order.get(minimum_plan, 0)

    async def _check(user: dict = Depends(get_current_user)) -> dict:
        user_plan = user.get("plan", "foundation")
        user_level = plan_order.get(user_plan, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Plan '{user_plan}' does not include this feature. "
                       f"Upgrade to '{minimum_plan}' or higher.",
            )
        return user

    return _check
