"""
通知渠道管理 API 模块

提供通知渠道相关的管理接口，包括：
- 列出所有可用的通知器类型
- 测试指定通知器是否正常工作
- 创建新的通知渠道
- 列出当前用户的所有通知渠道
- 删除指定的通知渠道

所有端点挂载在 /api/notifications 路径下，需要用户已登录。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.notification import NotificationChannel
from app.schemas.notification import (
    NotificationChannelCreate, NotificationChannelResponse, NotificationTestRequest,
)
from app.core.security import get_current_user
from app.core.notification_engine import notification_engine

# 创建通知管理路由器，路径前缀为 /api/notifications，标签为 notifications
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/notifiers")
async def list_notifiers(current_user: User = Depends(get_current_user)):
    """
    列出所有可用的通知器类型

    返回系统中已注册的所有通知器类型列表（如邮件、Webhook、Telegram 等）。

    Args:
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        list: 通知器类型列表，每个元素包含类型名称和描述等信息
    """
    return notification_engine.list_notifiers()


@router.post("/test")
async def test_notifier(
    data: NotificationTestRequest,
    current_user: User = Depends(get_current_user),
):
    """
    测试通知器是否正常工作

    根据指定的通知器类型和配置，发送一条测试通知以验证配置是否正确。

    Args:
        data: 通知测试请求数据，包含通知器类型和配置信息
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        dict: 包含 success 字段，表示测试是否成功

    Raises:
        HTTPException: 当通知器类型不存在时返回 400 错误
    """
    # 根据类型获取对应的通知器实例
    notifier = notification_engine.get(data.type)
    if not notifier:
        raise HTTPException(status_code=400, detail="Unknown notifier type")
    # 执行测试通知发送
    success = await notifier.test(data.config)
    return {"success": success}


@router.post("/channels", response_model=NotificationChannelResponse, status_code=201)
async def create_channel(
    data: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建通知渠道

    为当前用户创建一个新的通知渠道，绑定指定的通知器类型和配置。

    Args:
        data: 通知渠道创建数据，包含类型、配置和启用状态
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        NotificationChannelResponse: 新创建的通知渠道信息
    """
    # 创建通知渠道对象，关联到当前用户
    channel = NotificationChannel(
        user_id=current_user.id,
        type=data.type,
        config=data.config,
        enabled=data.enabled,
    )
    # 保存到数据库
    db.add(channel)
    await db.flush()
    # 刷新以获取数据库自动生成的字段（如 id 和 created_at）
    await db.refresh(channel)
    return channel


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    列出当前用户的所有通知渠道

    查询并返回当前登录用户已创建的所有通知渠道。

    Args:
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        list[NotificationChannelResponse]: 通知渠道列表
    """
    # 查询属于当前用户的所有通知渠道
    result = await db.execute(
        select(NotificationChannel).where(NotificationChannel.user_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除指定的通知渠道

    删除当前用户拥有的指定通知渠道。只能删除属于自己的渠道。

    Args:
        channel_id: 要删除的通知渠道 ID
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        None: 成功删除返回 204 状态码（无内容）

    Raises:
        HTTPException: 当渠道不存在或不属于当前用户时返回 404 错误
    """
    # 查询渠道，同时验证渠道属于当前用户（防止越权删除）
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.user_id == current_user.id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404)
    # 从数据库中删除该渠道
    await db.delete(channel)
