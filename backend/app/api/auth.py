"""
认证 API 模块

提供用户认证相关的接口，包括：
- 用户注册（创建新用户）
- 用户登录（获取访问令牌）
- 获取当前登录用户信息

所有端点挂载在 /api/auth 路径下。
"""

from fastapi import APIRouter, Depends, status

from app.core.exceptions import APIException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.core.custom_route import CustomAPIRoute

# 创建认证路由器，路径前缀为 /api/auth，标签为 auth
router = APIRouter(prefix="/api/auth", tags=["auth"], route_class=CustomAPIRoute)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    用户注册端点

    接收用户名和密码，创建新用户。如果用户名已存在则返回 400 错误。
    第一个注册用户自动成为 admin，后续注册用户为普通 user。

    Args:
        data: 用户注册数据（用户名、密码）
        db: 异步数据库会话（通过依赖注入获取）

    Returns:
        UserResponse: 新创建的用户信息

    Raises:
        APIException: 当用户名已被注册时返回 400 错误
    """
    # 查询数据库检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise APIException("用户名已存在", 400)

    # 判断是否为第一个用户：查询数据库中是否已有用户
    count_result = await db.execute(select(func.count(User.id)))
    is_first_user = count_result.scalar_one() == 0

    # 创建新用户对象，密码经过哈希处理
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role="admin" if is_first_user else "user",
    )
    # 将用户添加到数据库会话
    db.add(user)
    # 刷新会话以获取自动生成的字段（如 id）
    await db.flush()
    # 刷新用户对象以获取数据库中的最新数据
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    用户登录端点

    验证用户名和密码，成功后返回 JWT 访问令牌。

    Args:
        data: 用户登录数据（用户名、密码）
        db: 异步数据库会话（通过依赖注入获取）

    Returns:
        TokenResponse: 包含 access_token 的响应

    Raises:
        APIException: 当用户名或密码错误时返回 401 错误
    """
    # 根据用户名查询用户
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    # 验证用户是否存在以及密码是否正确
    if not user or not verify_password(data.password, user.hashed_password):
        raise APIException("用户名或密码错误", 401)

    # 生成 JWT 访问令牌，以用户 ID 作为主题（sub）
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/has-users")
async def has_users(db: AsyncSession = Depends(get_db)):
    """
    检查系统中是否已有注册用户。

    用于前端判断是否为首次使用（无用户时展示注册界面）。

    Args:
        db: 异步数据库会话

    Returns:
        dict: {"has_users": bool}
    """
    count_result = await db.execute(select(func.count(User.id)))
    return {"has_users": count_result.scalar_one() > 0}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    获取当前登录用户信息

    通过解析请求头中的 JWT 令牌获取当前用户信息。
    需要用户已登录（携带有效的访问令牌）。

    Args:
        current_user: 当前登录用户（通过依赖注入从 JWT 令牌解析获得）

    Returns:
        UserResponse: 当前用户的信息
    """
    return current_user
