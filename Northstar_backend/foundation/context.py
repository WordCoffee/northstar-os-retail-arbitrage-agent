"""Request context: environment, role, view context, customer preview.

Three orthogonal dimensions (owner decision 5). Preview never grants permissions
the real actor lacks; read-only by default; fully auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import Environment, Role, ViewContext
from .models import utcnow


@dataclass
class PreviewContext:
    preview_id: str
    actor_user_id: str
    target_organization_id: str
    target_role: Optional[str] = None
    started_at: datetime = field(default_factory=utcnow)
    ended_at: Optional[datetime] = None
    reason: str = ""
    read_only: bool = True
    active: bool = True


@dataclass
class RequestContext:
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    role: Optional[str] = None
    environment: str = Environment.PRODUCTION.value
    view_context: str = ViewContext.NORMAL.value
    preview: Optional[PreviewContext] = None
    request_id: Optional[str] = None
    auth_method: Optional[str] = None  # "jwt" | "dev_shim"

    # -- effective values under preview ---------------------------------------

    @property
    def effective_organization_id(self) -> Optional[str]:
        if self.preview and self.preview.active:
            return self.preview.target_organization_id
        return self.organization_id

    @property
    def effective_role(self) -> Optional[str]:
        """Preview shows the target role but can never exceed the real role."""
        if self.preview and self.preview.active and self.preview.target_role:
            real = self.role or Role.VIEWER.value
            return _min_role(real, self.preview.target_role)
        return self.role

    @property
    def is_preview(self) -> bool:
        return bool(self.preview and self.preview.active)

    @property
    def is_sandbox(self) -> bool:
        return self.environment == Environment.SANDBOX.value

    def allow_write(self) -> bool:
        """Preview is read-only: writes to production are blocked while previewing."""
        if self.is_preview and self.preview and self.preview.read_only:
            return False
        return True


_ROLE_RANK = {
    Role.VIEWER.value: 0,
    Role.ANALYST.value: 1,
    Role.OPERATOR.value: 2,
    Role.ORGANIZATION_ADMIN.value: 3,
    Role.ORGANIZATION_OWNER.value: 4,
    Role.INTERNAL_PLATFORM_ADMIN.value: 5,
}


def _min_role(a: str, b: str) -> str:
    return a if _ROLE_RANK.get(a, -1) <= _ROLE_RANK.get(b, -1) else b


def build_context(
    *,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    role: Optional[str] = None,
    environment: str = Environment.PRODUCTION.value,
    view_context: str = ViewContext.NORMAL.value,
    preview: Optional[PreviewContext] = None,
    request_id: Optional[str] = None,
    auth_method: Optional[str] = None,
) -> RequestContext:
    ctx = RequestContext(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        environment=environment,
        view_context=view_context,
        preview=preview,
        request_id=request_id,
        auth_method=auth_method,
    )
    if preview and preview.active:
        ctx.view_context = ViewContext.AUDITED_CUSTOMER_PREVIEW.value
    return ctx