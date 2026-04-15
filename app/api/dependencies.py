from fastapi import Header, HTTPException, status
from app.core.config import get_settings

settings = get_settings()


async def verify_tenant(
    x_tenant_id: str = Header(..., description="Tenant identifier: amazon, flipkart, or myntra"),
    x_api_key: str = Header(..., description="Tenant API key"),
) -> str:
    """
    FastAPI dependency — validates tenant identity on every request.

    How it works:
    - Reads X-Tenant-ID and X-API-Key headers
    - Checks the key maps to the claimed tenant in TENANT_API_KEYS env var
    - Returns verified tenant_id for use in the route handler

    Why dependency injection (not middleware):
    - Only auth-required routes declare this dependency
    - /health doesn't need auth — stays public
    - FastAPI auto-documents required headers in Swagger UI
    """
    tenant_key_map = settings.tenant_key_map

    if x_api_key not in tenant_key_map:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if tenant_key_map[x_api_key] != x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key does not match tenant ID",
        )

    return x_tenant_id