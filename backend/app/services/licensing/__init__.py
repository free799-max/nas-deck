"""授权服务与 FastAPI 门禁依赖。"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.licensing.service import licensing_service


async def require_license(db: AsyncSession = Depends(get_db)) -> dict:
    return await licensing_service.require_valid(db)


__all__ = ["licensing_service", "require_license"]
