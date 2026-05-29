"""
插件实例管理 API 模块

提供插件实例相关的管理接口，包括：
- 列出所有可用的插件类型
- 创建新的插件实例（需要 admin 角色）
- 列出所有插件实例
- 删除指定插件实例（需要 admin 角色）

所有端点挂载在 /api/plugins 路径下，需要用户已登录。
创建和删除操作额外需要 admin 角色权限。
"""

from fastapi import APIRouter, Depends, status

from app.core.exceptions import APIException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.plugin import PluginInstance
from app.schemas.plugin import PluginInstanceCreate, PluginInstanceResponse, PluginInfo
from app.core.security import get_current_user
from app.core.plugin_loader import plugin_loader

# 创建插件管理路由器，路径前缀为 /api/plugins，标签为 plugins
router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("/available", response_model=list[PluginInfo])
async def list_available_plugins(current_user: User = Depends(get_current_user)):
    """
    列出所有可用的插件类型

    返回系统中已加载的所有插件类型信息，包括插件名称和描述等。

    Args:
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        list[PluginInfo]: 可用插件信息列表
    """
    return plugin_loader.list_plugins()


@router.post("/instances", response_model=PluginInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_instance(
    data: PluginInstanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建插件实例

    创建一个新的插件实例。此操作需要 admin 角色。
    插件实例创建后默认为启用状态。

    Args:
        data: 插件实例创建数据，包含插件名称、显示名称和配置
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        PluginInstanceResponse: 新创建的插件实例信息

    Raises:
        APIException: 当用户不是 admin 角色时返回 403 错误
    """
    # 权限检查：只有 admin 角色才能创建插件实例
    if current_user.role != "admin":
        raise APIException("权限不足", 403)
    # 创建插件实例对象，默认为启用状态
    instance = PluginInstance(
        plugin_name=data.plugin_name,
        display_name=data.display_name,
        config=data.config,
        enabled=True,
    )
    # 保存到数据库
    db.add(instance)
    await db.flush()
    # 刷新以获取数据库自动生成的字段
    await db.refresh(instance)
    return instance


@router.get("/instances", response_model=list[PluginInstanceResponse])
async def list_instances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    列出所有插件实例

    返回系统中所有已创建的插件实例列表。

    Args:
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        list[PluginInstanceResponse]: 插件实例列表
    """
    # 查询所有插件实例（不过滤用户，返回全局列表）
    result = await db.execute(select(PluginInstance))
    return result.scalars().all()


@router.delete("/instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除指定插件实例

    根据 ID 删除指定的插件实例。此操作需要 admin 角色。

    Args:
        instance_id: 要删除的插件实例 ID
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        None: 成功删除返回 204 状态码（无内容）

    Raises:
        APIException: 当用户不是 admin 角色时返回 403 错误
        APIException: 当插件实例不存在时返回 404 错误
    """
    # 权限检查：只有 admin 角色才能删除插件实例
    if current_user.role != "admin":
        raise APIException("权限不足", 403)
    # 查询指定 ID 的插件实例
    result = await db.execute(select(PluginInstance).where(PluginInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if not instance:
        raise APIException("插件实例不存在", 404)
    # 从数据库中删除该实例
    await db.delete(instance)
