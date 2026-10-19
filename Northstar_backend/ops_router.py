"""Read-only operational status surface (N-2).

Deliberately thin: all logic lives in ``ops_status`` (pure, injectable, no FastAPI),
so the status logic can be unit-tested without an app, a GPU or a network.

Authenticated with the same studio account dependency as the rest of the product
surface — operational state is the operator's data, not public.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from design_studio_api import studio_account
import ops_status

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/status")
def ops_status_endpoint(acct: str = Depends(studio_account)):
    """Measured operational status. Every null is an explicit 'could not measure'."""
    return ops_status.collect()
