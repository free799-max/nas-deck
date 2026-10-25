"""本机授权管理 API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.custom_route import CustomAPIRoute
from app.core.security import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.license import LicenseActivateRequest, LicenseStatusResponse
from app.services.licensing import licensing_service

router = APIRouter(prefix="/api/license", tags=["license"], route_class=CustomAPIRoute)


@router.get("/status", response_model=LicenseStatusResponse)
async def get_license_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await licensing_service.get_status(
        db, include_license_key=current_user.role == "admin"
    )


@router.post("/activate", response_model=LicenseStatusResponse)
async def activate_license(
    data: LicenseActivateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return await licensing_service.activate(db, data.license_key, data.device_name)


@router.post("/refresh", response_model=LicenseStatusResponse)
async def refresh_license(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return await licensing_service.refresh(db)


@router.post("/deactivate", response_model=LicenseStatusResponse)
async def deactivate_license(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return await licensing_service.deactivate(db)
