"""Tenant context propagation for request-scoped multi-tenancy."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_tenant_id: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)


def set_tenant_id(tenant_id: Optional[str]) -> None:
    _tenant_id.set(tenant_id)


def get_tenant_id() -> Optional[str]:
    return _tenant_id.get()


def require_tenant_id() -> str:
    tenant_id = _tenant_id.get()
    if not tenant_id:
        raise ValueError("Missing tenant context")
    return tenant_id
