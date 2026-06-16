"""Docker 管理 API 子包。

所有子路由统一挂载在 /api/docker 路径下。
"""

from fastapi import APIRouter

from app.api.docker import compose, containers, host, images, registries
from app.core.custom_route import CustomAPIRoute

router = APIRouter(
    prefix="/api/docker",
    tags=["docker"],
    route_class=CustomAPIRoute,
)

# 子路由内部已包含完整路径（如 /containers、/images 等），因此 include 时不加前缀
router.include_router(containers.router)
router.include_router(images.router)
router.include_router(registries.router)
router.include_router(compose.router)
router.include_router(host.router)
