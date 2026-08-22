"""Tenant context propagation for request-scoped structured logging.

set_tenant_id() is called by main.py's logging middleware so request logs
can be tagged with the acting user. Actual data-isolation enforcement (which
is the thing that matters) happens explicitly via the tenant_id/session_id
arguments threaded through RAGService and PgVectorStore — not via this
context var, so it intentionally exposes no getter beyond logging.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_tenant_id: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)


def set_tenant_id(tenant_id: Optional[str]) -> None:
    _tenant_id.set(tenant_id)
