"""
FastAPI Dependencies - Common dependency injection patterns
"""
from typing import Optional
from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user, TenantContext
from db.session import get_db


async def get_user_agent(user_agent: Optional[str] = Header(None)) -> Optional[str]:
    """Get user agent from headers"""
    return user_agent


async def get_request_id(x_request_id: Optional[str] = Header(None)) -> Optional[str]:
    """Get request ID from headers"""
    return x_request_id


async def verify_tenant_access(
    tenant_id: str,
    context: TenantContext = Depends(get_current_user)
) -> bool:
    """Verify user has access to specified tenant"""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied to this tenant"
        )
    return True


class DatabaseDependency:
    """Database session dependency with automatic cleanup"""
    
    def __init__(self):
        self.session: Optional[AsyncSession] = None
    
    async def __call__(self) -> AsyncSession:
        async for session in get_db():
            self.session = session
            return session


# Common dependency combinations
async def get_authenticated_db_session(
    context: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get authenticated user and database session"""
    return context, db


async def require_admin_with_db(
    context: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Require admin permission and return context + db session"""
    if not context.has_permission("admin"):
        raise HTTPException(
            status_code=403,
            detail="Admin permission required"
        )
    return context, db