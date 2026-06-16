"""Docker 宿主机信息相关 API。"""

from fastapi import APIRouter, Depends

from app.core.custom_route import CustomAPIRoute
from app.core.exceptions import APIException
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.docker import HostInfo
from app.core.docker_manager import docker_manager

router = APIRouter(route_class=CustomAPIRoute)


@router.get("/host/info", response_model=HostInfo)
async def get_host_info(current_user: User = Depends(get_current_user)):
    """获取 Docker 宿主机综合信息。"""
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    info = docker_manager.get_host_info()
    if not info:
        raise APIException("Docker 不可用", 503)
    return info
