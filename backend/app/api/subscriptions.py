"""
订阅管理 API 模块

提供用户订阅相关的管理接口，包括：
- 创建新订阅
- 列出当前用户的所有订阅
- 删除指定订阅

所有端点挂载在 /api/subscriptions 路径下，需要用户已登录。
订阅数据按用户隔离，用户只能操作自己的订阅。
"""

from fastapi import APIRouter, Depends, status

from app.core.exceptions import APIException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse
from app.core.security import get_current_user

# 创建订阅管理路由器，路径前缀为 /api/subscriptions，标签为 subscriptions
router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建用户订阅

    为当前用户创建一条新的订阅记录，订阅状态默认为 active（活跃）。

    Args:
        data: 订阅创建数据，包含插件实例 ID、订阅项 ID、标题和元数据
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        SubscriptionResponse: 新创建的订阅信息
    """
    # 创建订阅对象，关联到当前用户，状态默认为 active
    sub = Subscription(
        user_id=current_user.id,
        instance_id=data.instance_id,
        item_id=data.item_id,
        item_title=data.item_title,
        item_meta=data.item_meta,
        status="active",
    )
    # 保存到数据库
    db.add(sub)
    await db.flush()
    # 刷新以获取数据库自动生成的字段
    await db.refresh(sub)
    return sub


@router.get("", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    列出当前用户的所有订阅

    查询并返回当前登录用户的所有订阅记录。

    Args:
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        list[SubscriptionResponse]: 当前用户的订阅列表
    """
    # 查询属于当前用户的所有订阅记录
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    sub_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除指定订阅

    删除当前用户拥有的指定订阅。只能删除属于自己的订阅。

    Args:
        sub_id: 要删除的订阅 ID
        db: 异步数据库会话（通过依赖注入获取）
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        None: 成功删除返回 204 状态码（无内容）

    Raises:
        APIException: 当订阅不存在或不属于当前用户时返回 404 错误
    """
    # 查询订阅，同时验证订阅属于当前用户（防止越权删除）
    result = await db.execute(
        select(Subscription).where(Subscription.id == sub_id, Subscription.user_id == current_user.id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise APIException("订阅不存在", 404)
    # 从数据库中删除该订阅
    await db.delete(sub)
