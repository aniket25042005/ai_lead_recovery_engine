from typing import Optional
from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db


def get_tenant_id_header(x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID")) -> Optional[str]:
    """
    Extracts tenant ID from standard header for tenant isolation.
    """
    return x_tenant_id


def require_tenant_id(x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID")) -> str:
    """
    Strict dependency requiring X-Tenant-ID header to guarantee tenant isolation.
    """
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'X-Tenant-ID' is required for multi-tenant isolation.",
        )
    return x_tenant_id.strip()
