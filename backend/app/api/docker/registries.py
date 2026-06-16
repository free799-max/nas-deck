"""镜像搜索接口配置（Registry）相关 API。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.custom_route import CustomAPIRoute
from app.core.exceptions import APIException
from app.core.security import get_current_user
from app.database import get_db
from app.models.docker import DockerMirrorConfig
from app.models.user import User
from app.schemas.docker import RegistryCreate, RegistryOut, RegistryUpdate

router = APIRouter(route_class=CustomAPIRoute)


@router.get("/registries", response_model=list[RegistryOut])
async def list_registries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有镜像搜索接口配置列表。"""
    result = await db.execute(select(DockerMirrorConfig).order_by(DockerMirrorConfig.id))
    configs = result.scalars().all()
    return configs


@router.post("/registries", response_model=RegistryOut)
async def create_registry(
    data: RegistryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建镜像搜索接口配置，第一条自动设为默认。"""
    config = DockerMirrorConfig(
        name=data.name,
        search_api_url=data.search_api_url,
        mirror_url=data.mirror_url,
        enable_mirror=data.enable_mirror,
        username=data.username,
        password=data.password,
    )
    count_result = await db.execute(select(DockerMirrorConfig))
    if not count_result.scalars().first():
        config.is_default = True
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/registries/{registry_id}", response_model=RegistryOut)
async def update_registry(
    registry_id: int,
    data: RegistryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新镜像搜索接口配置。"""
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/registries/{registry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_registry(
    registry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除镜像搜索接口配置。"""
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    if config.is_default:
        raise APIException("默认配置不允许删除，请先切换默认配置", 400)
    await db.delete(config)
    await db.commit()


@router.post("/registries/{registry_id}/set-default", response_model=RegistryOut)
async def set_default_registry(
    registry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将指定配置设为默认。"""
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    others = await db.execute(
        select(DockerMirrorConfig).where(
            DockerMirrorConfig.is_default == True,
            DockerMirrorConfig.id != registry_id,
        )
    )
    for other in others.scalars().all():
        other.is_default = False
    config.is_default = True
    await db.commit()
    await db.refresh(config)
    return config
