# EverySub 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个内容订阅聚合平台，通过微内核插件架构对接 Jellyfin/Komga/MoviePilot 等开源项目，支持 Docker Sidecar 管理和多渠道通知。

**Architecture:** 单体微内核架构。FastAPI 后端通过 importlib 动态加载插件模块，每个插件实现统一的 BasePlugin 接口。前端 React + shadcn/ui 通过 REST API 与后端交互。APScheduler 驱动定时轮询，docker-py 管理 sidecar 容器。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, APScheduler, docker-py, JWT | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query

---

## Task 1: 后端项目骨架 + 数据库基础

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/requirements.txt`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

**Step 1: 创建 requirements.txt**

```txt
fastapi==0.115.12
uvicorn[standard]==0.34.2
sqlalchemy==2.0.40
alembic==1.15.2
apscheduler==3.11.0
python-jose[cryptography]==3.4.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.20
httpx==0.28.1
docker==7.1.0
pydantic==2.11.1
pydantic-settings==2.9.1
pytest==8.3.5
pytest-asyncio==0.25.3
aiosqlite==0.21.0
```

**Step 2: 创建配置模块 `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "EverySub"
    DATABASE_URL: str = "sqlite+aiosqlite:///./everysub.db"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PLUGIN_DIR: str = "app/plugins"

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Step 3: 创建数据库模块 `backend/app/database.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

**Step 4: 创建 FastAPI 入口 `backend/app/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
```

**Step 5: 编写测试 `backend/tests/conftest.py` 和 `backend/tests/test_health.py`**

conftest.py:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

test_health.py:
```python
import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "EverySub"
```

**Step 6: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: PASS

**Step 7: 提交**

```bash
git add backend/
git commit -m "feat: backend skeleton with FastAPI, config, database, health endpoint"
```

---

## Task 2: 数据模型 (SQLAlchemy Models)

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/plugin.py`
- Create: `backend/app/models/subscription.py`
- Create: `backend/app/models/notification.py`
- Create: `backend/app/models/docker.py`
- Create: `backend/tests/test_models.py`

**Step 1: 编写模型测试 `backend/tests/test_models.py`**

```python
import pytest
from sqlalchemy import select

from app.database import async_session, init_db, engine, Base
from app.models.user import User
from app.models.plugin import PluginInstance
from app.models.subscription import Subscription, UpdateLog
from app.models.notification import NotificationChannel
from app.models.docker import DockerContainer


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_create_user():
    async with async_session() as session:
        user = User(username="admin", hashed_password="hashed", role="admin")
        session.add(user)
        await session.commit()
        result = await session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 1
        assert users[0].username == "admin"


@pytest.mark.asyncio
async def test_create_plugin_instance():
    async with async_session() as session:
        instance = PluginInstance(
            plugin_name="jellyfin",
            display_name="My Jellyfin",
            config={"url": "http://localhost:8096", "api_key": "test"},
            enabled=True,
        )
        session.add(instance)
        await session.commit()
        result = await session.execute(select(PluginInstance))
        instances = result.scalars().all()
        assert len(instances) == 1
        assert instances[0].plugin_name == "jellyfin"


@pytest.mark.asyncio
async def test_subscription_with_update_log():
    async with async_session() as session:
        user = User(username="admin", hashed_password="hashed", role="admin")
        instance = PluginInstance(
            plugin_name="jellyfin",
            display_name="My Jellyfin",
            config={},
            enabled=True,
        )
        session.add_all([user, instance])
        await session.flush()

        sub = Subscription(
            user_id=user.id,
            instance_id=instance.id,
            item_id="movie-123",
            item_title="Test Movie",
            item_meta={"year": 2026},
            status="active",
        )
        session.add(sub)
        await session.flush()

        log = UpdateLog(
            subscription_id=sub.id,
            title="New episode",
            content="Episode 5 released",
            notified=False,
        )
        session.add(log)
        await session.commit()

        result = await session.execute(select(UpdateLog))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].title == "New episode"
```

**Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL (models not yet created)

**Step 3: 实现 User 模型 `backend/app/models/user.py`**

```python
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    subscriptions = relationship("Subscription", back_populates="user")
    notification_channels = relationship("NotificationChannel", back_populates="user")
```

**Step 4: 实现 PluginInstance 模型 `backend/app/models/plugin.py`**

```python
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PluginInstance(Base):
    __tablename__ = "plugin_instances"

    id: Mapped[int] = mapped_column(primary_key=True)
    plugin_name: Mapped[str] = mapped_column(String(50), index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    docker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    subscriptions = relationship("Subscription", back_populates="instance")
    container = relationship("DockerContainer", back_populates="instance", uselist=False)
```

**Step 5: 实现 Subscription + UpdateLog `backend/app/models/subscription.py`**

```python
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, JSON, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    instance_id: Mapped[int] = mapped_column(ForeignKey("plugin_instances.id"))
    item_id: Mapped[str] = mapped_column(String(255))
    item_title: Mapped[str] = mapped_column(String(255))
    item_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="subscriptions")
    instance = relationship("PluginInstance", back_populates="subscriptions")
    update_logs = relationship("UpdateLog", back_populates="subscription")


class UpdateLog(Base):
    __tablename__ = "update_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notified: Mapped[bool] = mapped_column(Boolean, default=False)

    subscription = relationship("Subscription", back_populates="update_logs")
```

**Step 6: 实现 NotificationChannel `backend/app/models/notification.py`**

```python
from datetime import datetime

from sqlalchemy import String, ForeignKey, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(20))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="notification_channels")
```

**Step 7: 实现 DockerContainer `backend/app/models/docker.py`**

```python
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DockerContainer(Base):
    __tablename__ = "docker_containers"

    id: Mapped[int] = mapped_column(primary_key=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey("plugin_instances.id"), unique=True)
    container_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    health: Mapped[str] = mapped_column(String(20), default="unknown")
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    instance = relationship("PluginInstance", back_populates="container")
```

**Step 8: 创建 `backend/app/models/__init__.py`**

```python
from app.models.user import User
from app.models.plugin import PluginInstance
from app.models.subscription import Subscription, UpdateLog
from app.models.notification import NotificationChannel
from app.models.docker import DockerContainer

__all__ = [
    "User", "PluginInstance", "Subscription", "UpdateLog",
    "NotificationChannel", "DockerContainer",
]
```

**Step 9: 更新 `backend/app/database.py` 的 init_db**

在 `create_all` 之前添加 `import app.models`：
```python
async def init_db():
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

**Step 10: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: ALL PASS

**Step 11: 提交**

```bash
git add backend/app/models/ backend/tests/test_models.py backend/app/database.py
git commit -m "feat: add SQLAlchemy models for all core entities"
```

---

<!-- PLAN_CONTINUE_1 -->

## Task 3: 用户认证 (JWT Auth)

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/security.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/tests/test_auth.py`

**Step 1: 编写认证测试 `backend/tests/test_auth.py`**

```python
import pytest


@pytest.mark.asyncio
async def test_register_user(client):
    resp = await client.post("/api/auth/register", json={
        "username": "admin",
        "password": "admin123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "admin"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_user(client):
    await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    resp = await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "admin", "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client):
    await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    token = login_resp.json()["access_token"]
    resp = await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
```

**Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: FAIL

**Step 3: 实现 Pydantic schemas `backend/app/schemas/user.py`**

```python
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

**Step 4: 实现安全模块 `backend/app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import User

    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user
```

**Step 5: 实现认证路由 `backend/app/api/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role="admin",  # first user is admin
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

**Step 6: 注册路由到 main.py**

在 `backend/app/main.py` 中添加：
```python
from app.api.auth import router as auth_router

app.include_router(auth_router)
```

**Step 7: 更新 conftest.py 支持数据库重置**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.main import app
from app.database import engine, Base


@pytest.fixture(autouse=True)
async def reset_db():
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

**Step 8: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: ALL PASS

**Step 9: 提交**

```bash
git add backend/app/schemas/ backend/app/core/ backend/app/api/ backend/tests/
git commit -m "feat: add JWT authentication with register, login, and me endpoints"
```

---

<!-- PLAN_CONTINUE_2 -->

## Task 4: 插件系统核心 (Plugin Loader + BasePlugin)

**Files:**
- Create: `backend/app/plugins/__init__.py`
- Create: `backend/app/plugins/base.py`
- Create: `backend/app/core/plugin_loader.py`
- Create: `backend/tests/test_plugin_loader.py`

**Step 1: 编写插件加载器测试 `backend/tests/test_plugin_loader.py`**

```python
import pytest

from app.plugins.base import BasePlugin, Source, Item, Update
from app.core.plugin_loader import PluginLoader


class FakePlugin(BasePlugin):
    name = "fake"
    display_name = "Fake Plugin"
    version = "1.0.0"
    description = "A fake plugin for testing"
    config_schema = {"type": "object", "properties": {"url": {"type": "string"}}}

    async def test_connection(self, config: dict) -> bool:
        return config.get("url") == "http://valid"

    async def get_sources(self, config: dict) -> list[Source]:
        return [Source(id="lib-1", name="Library 1")]

    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        return [Item(id="item-1", title="Test Item", source_id=source_id, meta={})]

    async def check_updates(self, config: dict, subscriptions: list) -> list[Update]:
        return [Update(subscription_id=1, title="New content", content="Details")]


def test_base_plugin_interface():
    plugin = FakePlugin()
    assert plugin.name == "fake"
    assert plugin.config_schema is not None


@pytest.mark.asyncio
async def test_plugin_test_connection():
    plugin = FakePlugin()
    assert await plugin.test_connection({"url": "http://valid"}) is True
    assert await plugin.test_connection({"url": "http://invalid"}) is False


@pytest.mark.asyncio
async def test_plugin_get_sources():
    plugin = FakePlugin()
    sources = await plugin.get_sources({})
    assert len(sources) == 1
    assert sources[0].name == "Library 1"


def test_plugin_loader_register():
    loader = PluginLoader()
    loader.register(FakePlugin)
    assert "fake" in loader.plugins
    assert loader.get("fake") is not None


def test_plugin_loader_list():
    loader = PluginLoader()
    loader.register(FakePlugin)
    plugins = loader.list_plugins()
    assert len(plugins) == 1
    assert plugins[0]["name"] == "fake"
```

**Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_plugin_loader.py -v`
Expected: FAIL

**Step 3: 实现 BasePlugin 和数据类 `backend/app/plugins/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Source:
    id: str
    name: str
    meta: dict = field(default_factory=dict)


@dataclass
class Item:
    id: str
    title: str
    source_id: str
    meta: dict = field(default_factory=dict)


@dataclass
class Update:
    subscription_id: int
    title: str
    content: str


class BasePlugin(ABC):
    name: str
    display_name: str
    version: str
    description: str
    config_schema: dict

    @abstractmethod
    async def test_connection(self, config: dict) -> bool: ...

    @abstractmethod
    async def get_sources(self, config: dict) -> list[Source]: ...

    @abstractmethod
    async def get_items(self, config: dict, source_id: str) -> list[Item]: ...

    @abstractmethod
    async def check_updates(self, config: dict, subscriptions: list) -> list[Update]: ...
```

**Step 4: 实现 PluginLoader `backend/app/core/plugin_loader.py`**

```python
import importlib
import pkgutil
from typing import Type

from app.plugins.base import BasePlugin


class PluginLoader:
    def __init__(self):
        self.plugins: dict[str, BasePlugin] = {}

    def register(self, plugin_cls: Type[BasePlugin]):
        instance = plugin_cls()
        self.plugins[instance.name] = instance

    def get(self, name: str) -> BasePlugin | None:
        return self.plugins.get(name)

    def list_plugins(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "display_name": p.display_name,
                "version": p.version,
                "description": p.description,
                "config_schema": p.config_schema,
            }
            for p in self.plugins.values()
        ]

    def discover(self, package_path: str = "app.plugins"):
        """Auto-discover plugins from the plugins package."""
        try:
            package = importlib.import_module(package_path)
        except ModuleNotFoundError:
            return

        for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if not is_pkg:
                continue
            module = importlib.import_module(f"{package_path}.{module_name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                ):
                    self.register(attr)


# Global singleton
plugin_loader = PluginLoader()
```

**Step 5: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_plugin_loader.py -v`
Expected: ALL PASS

**Step 6: 提交**

```bash
git add backend/app/plugins/ backend/app/core/plugin_loader.py backend/tests/test_plugin_loader.py
git commit -m "feat: add plugin system with BasePlugin interface and PluginLoader"
```

---

<!-- PLAN_CONTINUE_3 -->

## Task 5: 插件管理 API + 订阅 API

**Files:**
- Create: `backend/app/schemas/plugin.py`
- Create: `backend/app/schemas/subscription.py`
- Create: `backend/app/api/plugins.py`
- Create: `backend/app/api/subscriptions.py`
- Create: `backend/tests/test_plugins_api.py`
- Create: `backend/tests/test_subscriptions_api.py`

**Step 1: 编写插件管理 API 测试 `backend/tests/test_plugins_api.py`**

```python
import pytest


async def get_auth_header(client):
    await client.post("/api/auth/register", json={"username": "admin", "password": "admin123"})
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_available_plugins(client):
    headers = await get_auth_header(client)
    resp = await client.get("/api/plugins/available", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_plugin_instance(client):
    headers = await get_auth_header(client)
    resp = await client.post("/api/plugins/instances", headers=headers, json={
        "plugin_name": "jellyfin",
        "display_name": "My Jellyfin",
        "config": {"url": "http://localhost:8096", "api_key": "test"},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["plugin_name"] == "jellyfin"
    assert data["display_name"] == "My Jellyfin"


@pytest.mark.asyncio
async def test_list_plugin_instances(client):
    headers = await get_auth_header(client)
    await client.post("/api/plugins/instances", headers=headers, json={
        "plugin_name": "jellyfin",
        "display_name": "My Jellyfin",
        "config": {},
    })
    resp = await client.get("/api/plugins/instances", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_plugin_instance(client):
    headers = await get_auth_header(client)
    create_resp = await client.post("/api/plugins/instances", headers=headers, json={
        "plugin_name": "jellyfin",
        "display_name": "My Jellyfin",
        "config": {},
    })
    instance_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/plugins/instances/{instance_id}", headers=headers)
    assert resp.status_code == 204
```

**Step 2: 编写订阅 API 测试 `backend/tests/test_subscriptions_api.py`**

```python
import pytest


async def setup_auth_and_instance(client):
    await client.post("/api/auth/register", json={"username": "admin", "password": "admin123"})
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    inst_resp = await client.post("/api/plugins/instances", headers=headers, json={
        "plugin_name": "jellyfin",
        "display_name": "My Jellyfin",
        "config": {},
    })
    return headers, inst_resp.json()["id"]


@pytest.mark.asyncio
async def test_create_subscription(client):
    headers, instance_id = await setup_auth_and_instance(client)
    resp = await client.post("/api/subscriptions", headers=headers, json={
        "instance_id": instance_id,
        "item_id": "movie-123",
        "item_title": "Test Movie",
        "item_meta": {"year": 2026},
    })
    assert resp.status_code == 201
    assert resp.json()["item_title"] == "Test Movie"


@pytest.mark.asyncio
async def test_list_subscriptions(client):
    headers, instance_id = await setup_auth_and_instance(client)
    await client.post("/api/subscriptions", headers=headers, json={
        "instance_id": instance_id,
        "item_id": "movie-123",
        "item_title": "Test Movie",
        "item_meta": {},
    })
    resp = await client.get("/api/subscriptions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_subscription(client):
    headers, instance_id = await setup_auth_and_instance(client)
    create_resp = await client.post("/api/subscriptions", headers=headers, json={
        "instance_id": instance_id,
        "item_id": "movie-123",
        "item_title": "Test Movie",
        "item_meta": {},
    })
    sub_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/subscriptions/{sub_id}", headers=headers)
    assert resp.status_code == 204
```

**Step 3: 实现 Pydantic schemas**

`backend/app/schemas/plugin.py`:
```python
from pydantic import BaseModel


class PluginInstanceCreate(BaseModel):
    plugin_name: str
    display_name: str
    config: dict = {}
    manage_docker: bool = False


class PluginInstanceResponse(BaseModel):
    id: int
    plugin_name: str
    display_name: str
    config: dict
    docker_id: str | None
    enabled: bool

    model_config = {"from_attributes": True}


class PluginInfo(BaseModel):
    name: str
    display_name: str
    version: str
    description: str
    config_schema: dict
```

`backend/app/schemas/subscription.py`:
```python
from datetime import datetime
from pydantic import BaseModel


class SubscriptionCreate(BaseModel):
    instance_id: int
    item_id: str
    item_title: str
    item_meta: dict = {}


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    instance_id: int
    item_id: str
    item_title: str
    item_meta: dict
    status: str
    last_checked: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

**Step 4: 实现插件管理路由 `backend/app/api/plugins.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.plugin import PluginInstance
from app.schemas.plugin import PluginInstanceCreate, PluginInstanceResponse, PluginInfo
from app.core.security import get_current_user
from app.core.plugin_loader import plugin_loader

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("/available", response_model=list[PluginInfo])
async def list_available_plugins(current_user: User = Depends(get_current_user)):
    return plugin_loader.list_plugins()


@router.post("/instances", response_model=PluginInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_instance(
    data: PluginInstanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instance = PluginInstance(
        plugin_name=data.plugin_name,
        display_name=data.display_name,
        config=data.config,
        enabled=True,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


@router.get("/instances", response_model=list[PluginInstanceResponse])
async def list_instances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(PluginInstance))
    return result.scalars().all()


@router.delete("/instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(PluginInstance).where(PluginInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    await db.delete(instance)
    await db.commit()
```

**Step 5: 实现订阅路由 `backend/app/api/subscriptions.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse
from app.core.security import get_current_user

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = Subscription(
        user_id=current_user.id,
        instance_id=data.instance_id,
        item_id=data.item_id,
        item_title=data.item_title,
        item_meta=data.item_meta,
        status="active",
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


@router.get("", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    result = await db.execute(
        select(Subscription).where(Subscription.id == sub_id, Subscription.user_id == current_user.id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.delete(sub)
    await db.commit()
```

**Step 6: 注册路由到 main.py**

```python
from app.api.plugins import router as plugins_router
from app.api.subscriptions import router as subscriptions_router

app.include_router(plugins_router)
app.include_router(subscriptions_router)
```

**Step 7: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_plugins_api.py tests/test_subscriptions_api.py -v`
Expected: ALL PASS

**Step 8: 提交**

```bash
git add backend/app/schemas/ backend/app/api/ backend/tests/
git commit -m "feat: add plugin instance and subscription CRUD APIs"
```

---

<!-- PLAN_CONTINUE_4 -->

## Task 6: 通知系统 (Notification Engine)

**Files:**
- Create: `backend/app/core/notification_engine.py`
- Create: `backend/app/core/notifiers/__init__.py`
- Create: `backend/app/core/notifiers/base.py`
- Create: `backend/app/core/notifiers/telegram.py`
- Create: `backend/app/core/notifiers/dingtalk.py`
- Create: `backend/app/core/notifiers/wechat_work.py`
- Create: `backend/app/schemas/notification.py`
- Create: `backend/app/api/notifications.py`
- Create: `backend/tests/test_notification_engine.py`

**Step 1: 编写通知引擎测试 `backend/tests/test_notification_engine.py`**

```python
import pytest

from app.core.notifiers.base import BaseNotifier
from app.core.notification_engine import NotificationEngine


class FakeNotifier(BaseNotifier):
    name = "fake"
    config_schema = {}

    def __init__(self):
        self.sent = []

    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        self.sent.append({"title": title, "content": content})
        return True

    async def test(self, config: dict) -> bool:
        return config.get("valid", False)


@pytest.mark.asyncio
async def test_notifier_send():
    notifier = FakeNotifier()
    result = await notifier.send("Test", "Content", config={})
    assert result is True
    assert len(notifier.sent) == 1


@pytest.mark.asyncio
async def test_notifier_test_connection():
    notifier = FakeNotifier()
    assert await notifier.test({"valid": True}) is True
    assert await notifier.test({"valid": False}) is False


def test_engine_register_and_list():
    engine = NotificationEngine()
    engine.register(FakeNotifier)
    notifiers = engine.list_notifiers()
    assert len(notifiers) == 1
    assert notifiers[0]["name"] == "fake"


@pytest.mark.asyncio
async def test_engine_send():
    engine = NotificationEngine()
    engine.register(FakeNotifier)
    result = await engine.send("fake", "Title", "Body", config={})
    assert result is True
```

**Step 2: 实现 BaseNotifier `backend/app/core/notifiers/base.py`**

```python
from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    name: str
    config_schema: dict

    @abstractmethod
    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool: ...

    @abstractmethod
    async def test(self, config: dict) -> bool: ...
```

**Step 3: 实现 NotificationEngine `backend/app/core/notification_engine.py`**

```python
from typing import Type

from app.core.notifiers.base import BaseNotifier


class NotificationEngine:
    def __init__(self):
        self.notifiers: dict[str, BaseNotifier] = {}

    def register(self, notifier_cls: Type[BaseNotifier]):
        instance = notifier_cls()
        self.notifiers[instance.name] = instance

    def get(self, name: str) -> BaseNotifier | None:
        return self.notifiers.get(name)

    def list_notifiers(self) -> list[dict]:
        return [
            {"name": n.name, "config_schema": n.config_schema}
            for n in self.notifiers.values()
        ]

    async def send(self, notifier_name: str, title: str, content: str, config: dict) -> bool:
        notifier = self.get(notifier_name)
        if not notifier:
            return False
        return await notifier.send(title, content, config=config)


notification_engine = NotificationEngine()
```

**Step 4: 实现三个通知渠道**

`backend/app/core/notifiers/telegram.py`:
```python
import httpx

from app.core.notifiers.base import BaseNotifier


class TelegramNotifier(BaseNotifier):
    name = "telegram"
    config_schema = {
        "type": "object",
        "properties": {
            "bot_token": {"type": "string", "title": "Bot Token"},
            "chat_id": {"type": "string", "title": "Chat ID"},
        },
        "required": ["bot_token", "chat_id"],
    }

    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": config["chat_id"],
                "text": f"*{title}*\n{content}",
                "parse_mode": "Markdown",
            })
            return resp.status_code == 200

    async def test(self, config: dict) -> bool:
        return await self.send("EverySub Test", "Notification channel connected!", config)
```

`backend/app/core/notifiers/dingtalk.py`:
```python
import httpx

from app.core.notifiers.base import BaseNotifier


class DingTalkNotifier(BaseNotifier):
    name = "dingtalk"
    config_schema = {
        "type": "object",
        "properties": {
            "webhook_url": {"type": "string", "title": "Webhook URL"},
        },
        "required": ["webhook_url"],
    }

    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.post(config["webhook_url"], json={
                "msgtype": "markdown",
                "markdown": {"title": title, "text": f"### {title}\n{content}"},
            })
            return resp.status_code == 200

    async def test(self, config: dict) -> bool:
        return await self.send("EverySub Test", "Notification channel connected!", config)
```

`backend/app/core/notifiers/wechat_work.py`:
```python
import httpx

from app.core.notifiers.base import BaseNotifier


class WeChatWorkNotifier(BaseNotifier):
    name = "wechat_work"
    config_schema = {
        "type": "object",
        "properties": {
            "webhook_url": {"type": "string", "title": "Webhook URL"},
        },
        "required": ["webhook_url"],
    }

    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.post(config["webhook_url"], json={
                "msgtype": "markdown",
                "markdown": {"content": f"### {title}\n{content}"},
            })
            return resp.status_code == 200

    async def test(self, config: dict) -> bool:
        return await self.send("EverySub Test", "Notification channel connected!", config)
```

**Step 5: 实现通知渠道 API schemas 和路由**

`backend/app/schemas/notification.py`:
```python
from pydantic import BaseModel


class NotificationChannelCreate(BaseModel):
    type: str
    config: dict = {}
    enabled: bool = True


class NotificationChannelResponse(BaseModel):
    id: int
    user_id: int
    type: str
    config: dict
    enabled: bool

    model_config = {"from_attributes": True}


class NotificationTestRequest(BaseModel):
    type: str
    config: dict
```

`backend/app/api/notifications.py`:
```python
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

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/notifiers")
async def list_notifiers(current_user: User = Depends(get_current_user)):
    return notification_engine.list_notifiers()


@router.post("/test")
async def test_notifier(
    data: NotificationTestRequest,
    current_user: User = Depends(get_current_user),
):
    notifier = notification_engine.get(data.type)
    if not notifier:
        raise HTTPException(status_code=400, detail="Unknown notifier type")
    success = await notifier.test(data.config)
    return {"success": success}


@router.post("/channels", response_model=NotificationChannelResponse, status_code=201)
async def create_channel(
    data: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    channel = NotificationChannel(
        user_id=current_user.id,
        type=data.type,
        config=data.config,
        enabled=data.enabled,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.user_id == current_user.id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404)
    await db.delete(channel)
    await db.commit()
```

**Step 6: 注册通知路由和通知渠道到 main.py**

```python
from app.api.notifications import router as notifications_router
from app.core.notification_engine import notification_engine
from app.core.notifiers.telegram import TelegramNotifier
from app.core.notifiers.dingtalk import DingTalkNotifier
from app.core.notifiers.wechat_work import WeChatWorkNotifier

app.include_router(notifications_router)

# Register notifiers
notification_engine.register(TelegramNotifier)
notification_engine.register(DingTalkNotifier)
notification_engine.register(WeChatWorkNotifier)
```

**Step 7: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_notification_engine.py -v`
Expected: ALL PASS

**Step 8: 提交**

```bash
git add backend/app/core/notifiers/ backend/app/core/notification_engine.py backend/app/schemas/notification.py backend/app/api/notifications.py backend/tests/
git commit -m "feat: add notification engine with Telegram, DingTalk, WeChatWork notifiers"
```

---

<!-- PLAN_CONTINUE_5 -->

## Task 7: Docker 管理模块

**Files:**
- Create: `backend/app/core/docker_manager.py`
- Create: `backend/app/schemas/docker.py`
- Create: `backend/app/api/docker.py`
- Create: `backend/tests/test_docker_manager.py`

**Step 1: 编写 Docker 管理器测试 `backend/tests/test_docker_manager.py`**

注意：Docker 相关测试需要 mock docker client，因为 CI/测试环境不一定有 Docker。

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.docker_manager import DockerManager


@pytest.fixture
def mock_docker_client():
    client = MagicMock()
    client.containers = MagicMock()
    client.ping = MagicMock(return_value=True)
    return client


def test_docker_manager_init():
    manager = DockerManager()
    assert manager is not None


@patch("app.core.docker_manager.docker")
def test_list_containers(mock_docker_module):
    mock_container = MagicMock()
    mock_container.id = "abc123"
    mock_container.name = "jellyfin"
    mock_container.status = "running"
    mock_container.attrs = {"State": {"Health": {"Status": "healthy"}}}

    mock_client = MagicMock()
    mock_client.containers.list.return_value = [mock_container]
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    containers = manager.list_containers()
    assert len(containers) == 1
    assert containers[0]["name"] == "jellyfin"
    assert containers[0]["status"] == "running"


@patch("app.core.docker_manager.docker")
def test_container_action_stop(mock_docker_module):
    mock_container = MagicMock()
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    manager.container_action("abc123", "stop")
    mock_container.stop.assert_called_once()


@patch("app.core.docker_manager.docker")
def test_container_action_restart(mock_docker_module):
    mock_container = MagicMock()
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    manager.container_action("abc123", "restart")
    mock_container.restart.assert_called_once()
```

**Step 2: 实现 DockerManager `backend/app/core/docker_manager.py`**

```python
import docker


class DockerManager:
    def __init__(self):
        try:
            self._client = docker.from_env()
        except docker.errors.DockerException:
            self._client = None

    @property
    def available(self) -> bool:
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    def list_containers(self, filters: dict | None = None) -> list[dict]:
        if not self._client:
            return []
        containers = self._client.containers.list(all=True, filters=filters)
        return [self._format_container(c) for c in containers]

    def get_container(self, container_id: str) -> dict | None:
        if not self._client:
            return None
        try:
            c = self._client.containers.get(container_id)
            return self._format_container(c)
        except docker.errors.NotFound:
            return None

    def container_action(self, container_id: str, action: str):
        if not self._client:
            raise RuntimeError("Docker not available")
        container = self._client.containers.get(container_id)
        getattr(container, action)()

    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        if not self._client:
            return ""
        container = self._client.containers.get(container_id)
        return container.logs(tail=tail).decode("utf-8", errors="replace")

    def _format_container(self, container) -> dict:
        health = "unknown"
        state = container.attrs.get("State", {})
        if "Health" in state:
            health = state["Health"].get("Status", "unknown")
        return {
            "id": container.id[:12],
            "name": container.name,
            "status": container.status,
            "health": health,
            "image": str(container.image.tags[0]) if container.image.tags else "unknown",
        }


docker_manager = DockerManager()
```

**Step 3: 实现 Docker API schemas 和路由**

`backend/app/schemas/docker.py`:
```python
from pydantic import BaseModel


class ContainerInfo(BaseModel):
    id: str
    name: str
    status: str
    health: str
    image: str


class ContainerAction(BaseModel):
    action: str  # start, stop, restart
```

`backend/app/api/docker.py`:
```python
from fastapi import APIRouter, Depends, HTTPException

from app.models.user import User
from app.schemas.docker import ContainerInfo, ContainerAction
from app.core.security import get_current_user
from app.core.docker_manager import docker_manager

router = APIRouter(prefix="/api/docker", tags=["docker"])


@router.get("/status")
async def docker_status(current_user: User = Depends(get_current_user)):
    return {"available": docker_manager.available}


@router.get("/containers", response_model=list[ContainerInfo])
async def list_containers(current_user: User = Depends(get_current_user)):
    return docker_manager.list_containers()


@router.get("/containers/{container_id}", response_model=ContainerInfo)
async def get_container(container_id: str, current_user: User = Depends(get_current_user)):
    container = docker_manager.get_container(container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    return container


@router.post("/containers/{container_id}/action")
async def container_action(
    container_id: str,
    data: ContainerAction,
    current_user: User = Depends(get_current_user),
):
    if data.action not in ("start", "stop", "restart"):
        raise HTTPException(status_code=400, detail="Invalid action")
    try:
        docker_manager.container_action(container_id, data.action)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers/{container_id}/logs")
async def container_logs(
    container_id: str,
    tail: int = 100,
    current_user: User = Depends(get_current_user),
):
    logs = docker_manager.get_container_logs(container_id, tail=tail)
    return {"logs": logs}
```

**Step 4: 注册路由到 main.py**

```python
from app.api.docker import router as docker_router
app.include_router(docker_router)
```

**Step 5: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_docker_manager.py -v`
Expected: ALL PASS

**Step 6: 提交**

```bash
git add backend/app/core/docker_manager.py backend/app/schemas/docker.py backend/app/api/docker.py backend/tests/test_docker_manager.py
git commit -m "feat: add Docker management module with container CRUD and actions"
```

---

<!-- PLAN_CONTINUE_6 -->

## Task 8: 定时调度器 (Scheduler)

**Files:**
- Create: `backend/app/core/scheduler.py`
- Create: `backend/tests/test_scheduler.py`

**Step 1: 编写调度器测试 `backend/tests/test_scheduler.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.scheduler import SubscriptionChecker


@pytest.mark.asyncio
async def test_check_updates_calls_plugin():
    mock_plugin = MagicMock()
    mock_plugin.check_updates = AsyncMock(return_value=[])

    checker = SubscriptionChecker()
    updates = await checker.check_plugin_updates(
        plugin=mock_plugin,
        config={"url": "http://test"},
        subscriptions=[],
    )
    mock_plugin.check_updates.assert_called_once()
    assert updates == []
```

**Step 2: 实现调度器 `backend/app/core/scheduler.py`**

```python
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import async_session
from app.models.plugin import PluginInstance
from app.models.subscription import Subscription, UpdateLog
from app.models.notification import NotificationChannel
from app.core.plugin_loader import plugin_loader
from app.core.notification_engine import notification_engine
from app.plugins.base import BasePlugin

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


class SubscriptionChecker:
    async def check_plugin_updates(
        self, plugin: BasePlugin, config: dict, subscriptions: list
    ):
        return await plugin.check_updates(config, subscriptions)

    async def run(self):
        async with async_session() as db:
            instances = (await db.execute(select(PluginInstance).where(PluginInstance.enabled == True))).scalars().all()

            for instance in instances:
                plugin = plugin_loader.get(instance.plugin_name)
                if not plugin:
                    continue

                subs = (await db.execute(
                    select(Subscription).where(
                        Subscription.instance_id == instance.id,
                        Subscription.status == "active",
                    )
                )).scalars().all()

                if not subs:
                    continue

                try:
                    updates = await self.check_plugin_updates(
                        plugin=plugin,
                        config=instance.config,
                        subscriptions=[{"id": s.id, "item_id": s.item_id} for s in subs],
                    )
                except Exception as e:
                    logger.error(f"Plugin {instance.plugin_name} check failed: {e}")
                    continue

                for update in updates:
                    log = UpdateLog(
                        subscription_id=update.subscription_id,
                        title=update.title,
                        content=update.content,
                        notified=False,
                    )
                    db.add(log)

                    # Find user's notification channels
                    sub = next((s for s in subs if s.id == update.subscription_id), None)
                    if sub:
                        channels = (await db.execute(
                            select(NotificationChannel).where(
                                NotificationChannel.user_id == sub.user_id,
                                NotificationChannel.enabled == True,
                            )
                        )).scalars().all()

                        for channel in channels:
                            try:
                                await notification_engine.send(
                                    channel.type, update.title, update.content, config=channel.config,
                                )
                                log.notified = True
                            except Exception as e:
                                logger.error(f"Notification failed: {e}")

            await db.commit()


subscription_checker = SubscriptionChecker()


def setup_scheduler():
    scheduler.add_job(subscription_checker.run, "interval", minutes=30, id="check_updates")
    scheduler.start()
```

**Step 3: 集成调度器到 main.py lifespan**

```python
from app.core.scheduler import setup_scheduler, scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    setup_scheduler()
    yield
    scheduler.shutdown()
```

**Step 4: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_scheduler.py -v`
Expected: ALL PASS

**Step 5: 提交**

```bash
git add backend/app/core/scheduler.py backend/tests/test_scheduler.py backend/app/main.py
git commit -m "feat: add APScheduler-based subscription update checker"
```

---

## Task 9: MVP 插件实现 (Jellyfin)

**Files:**
- Create: `backend/app/plugins/jellyfin/__init__.py`
- Create: `backend/app/plugins/jellyfin/plugin.py`
- Create: `backend/tests/test_jellyfin_plugin.py`

**Step 1: 编写 Jellyfin 插件测试 `backend/tests/test_jellyfin_plugin.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.plugins.jellyfin.plugin import JellyfinPlugin


@pytest.fixture
def plugin():
    return JellyfinPlugin()


def test_plugin_metadata(plugin):
    assert plugin.name == "jellyfin"
    assert plugin.display_name == "Jellyfin"
    assert "url" in str(plugin.config_schema)


@pytest.mark.asyncio
@patch("app.plugins.jellyfin.plugin.httpx.AsyncClient")
async def test_test_connection_success(mock_client_cls, plugin):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = await plugin.test_connection({"url": "http://localhost:8096", "api_key": "test"})
    assert result is True


@pytest.mark.asyncio
@patch("app.plugins.jellyfin.plugin.httpx.AsyncClient")
async def test_get_sources(mock_client_cls, plugin):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"Id": "lib1", "Name": "Movies", "CollectionType": "movies"},
    ]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    sources = await plugin.get_sources({"url": "http://localhost:8096", "api_key": "test"})
    assert len(sources) == 1
    assert sources[0].name == "Movies"
```

**Step 2: 实现 Jellyfin 插件 `backend/app/plugins/jellyfin/plugin.py`**

```python
import httpx

from app.plugins.base import BasePlugin, Source, Item, Update


class JellyfinPlugin(BasePlugin):
    name = "jellyfin"
    display_name = "Jellyfin"
    version = "1.0.0"
    description = "Jellyfin media server integration"
    config_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "title": "Server URL"},
            "api_key": {"type": "string", "title": "API Key"},
        },
        "required": ["url", "api_key"],
    }

    def _headers(self, config: dict) -> dict:
        return {"X-Emby-Token": config["api_key"]}

    async def test_connection(self, config: dict) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{config['url']}/System/Info",
                    headers=self._headers(config),
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def get_sources(self, config: dict) -> list[Source]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{config['url']}/Library/VirtualFolders",
                headers=self._headers(config),
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            return [
                Source(
                    id=lib["Id"] if "Id" in lib else lib["Name"],
                    name=lib["Name"],
                    meta={"collection_type": lib.get("CollectionType", "")},
                )
                for lib in resp.json()
            ]

    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{config['url']}/Items",
                headers=self._headers(config),
                params={
                    "ParentId": source_id,
                    "Recursive": "true",
                    "SortBy": "DateCreated",
                    "SortOrder": "Descending",
                    "Limit": 50,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            return [
                Item(
                    id=item["Id"],
                    title=item["Name"],
                    source_id=source_id,
                    meta={
                        "type": item.get("Type", ""),
                        "year": item.get("ProductionYear"),
                        "overview": item.get("Overview", ""),
                    },
                )
                for item in resp.json().get("Items", [])
            ]

    async def check_updates(self, config: dict, subscriptions: list) -> list[Update]:
        updates = []
        async with httpx.AsyncClient() as client:
            for sub in subscriptions:
                resp = await client.get(
                    f"{config['url']}/Items/{sub['item_id']}",
                    headers=self._headers(config),
                    params={"Fields": "DateLastMediaAdded"},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                # Check for new episodes/seasons
                if data.get("Type") == "Series":
                    episodes_resp = await client.get(
                        f"{config['url']}/Shows/{sub['item_id']}/Episodes",
                        headers=self._headers(config),
                        params={"SortBy": "DateCreated", "SortOrder": "Descending", "Limit": 1},
                        timeout=10,
                    )
                    if episodes_resp.status_code == 200:
                        episodes = episodes_resp.json().get("Items", [])
                        if episodes:
                            latest = episodes[0]
                            updates.append(Update(
                                subscription_id=sub["id"],
                                title=f"{data['Name']} - {latest['Name']}",
                                content=f"S{latest.get('ParentIndexNumber', '?')}E{latest.get('IndexNumber', '?')}",
                            ))
        return updates
```

`backend/app/plugins/jellyfin/__init__.py`:
```python
from app.plugins.jellyfin.plugin import JellyfinPlugin
```

**Step 3: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_jellyfin_plugin.py -v`
Expected: ALL PASS

**Step 4: 提交**

```bash
git add backend/app/plugins/jellyfin/ backend/tests/test_jellyfin_plugin.py
git commit -m "feat: add Jellyfin plugin implementation"
```

---

## Task 10: MVP 插件实现 (Komga + MoviePilot)

**Files:**
- Create: `backend/app/plugins/komga/__init__.py`
- Create: `backend/app/plugins/komga/plugin.py`
- Create: `backend/app/plugins/moviepilot/__init__.py`
- Create: `backend/app/plugins/moviepilot/plugin.py`
- Create: `backend/tests/test_komga_plugin.py`
- Create: `backend/tests/test_moviepilot_plugin.py`

**Step 1: 实现 Komga 插件 `backend/app/plugins/komga/plugin.py`**

```python
import httpx

from app.plugins.base import BasePlugin, Source, Item, Update


class KomgaPlugin(BasePlugin):
    name = "komga"
    display_name = "Komga"
    version = "1.0.0"
    description = "Komga comic/manga server integration"
    config_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "title": "Server URL"},
            "username": {"type": "string", "title": "Username"},
            "password": {"type": "string", "title": "Password"},
        },
        "required": ["url", "username", "password"],
    }

    def _auth(self, config: dict) -> tuple[str, str]:
        return (config["username"], config["password"])

    async def test_connection(self, config: dict) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{config['url']}/api/v1/libraries",
                    auth=self._auth(config),
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def get_sources(self, config: dict) -> list[Source]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{config['url']}/api/v1/libraries",
                auth=self._auth(config),
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            return [
                Source(id=lib["id"], name=lib["name"])
                for lib in resp.json()
            ]

    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{config['url']}/api/v1/series",
                auth=self._auth(config),
                params={"library_id": source_id, "size": 50, "sort": "lastModified,desc"},
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            return [
                Item(
                    id=s["id"],
                    title=s["metadata"]["title"],
                    source_id=source_id,
                    meta={"books_count": s.get("booksCount", 0)},
                )
                for s in resp.json().get("content", [])
            ]

    async def check_updates(self, config: dict, subscriptions: list) -> list[Update]:
        updates = []
        async with httpx.AsyncClient() as client:
            for sub in subscriptions:
                resp = await client.get(
                    f"{config['url']}/api/v1/series/{sub['item_id']}/books",
                    auth=self._auth(config),
                    params={"sort": "number,desc", "size": 1},
                    timeout=10,
                )
                if resp.status_code == 200:
                    books = resp.json().get("content", [])
                    if books:
                        latest = books[0]
                        updates.append(Update(
                            subscription_id=sub["id"],
                            title=f"New book: {latest['metadata']['title']}",
                            content=f"Number: {latest.get('number', '?')}",
                        ))
        return updates
```

**Step 2: 实现 MoviePilot 插件 `backend/app/plugins/moviepilot/plugin.py`**

```python
import httpx

from app.plugins.base import BasePlugin, Source, Item, Update


class MoviePilotPlugin(BasePlugin):
    name = "moviepilot"
    display_name = "MoviePilot"
    version = "1.0.0"
    description = "MoviePilot media automation integration"
    config_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "title": "Server URL"},
            "api_key": {"type": "string", "title": "API Key"},
        },
        "required": ["url", "api_key"],
    }

    def _headers(self, config: dict) -> dict:
        return {"Authorization": f"Bearer {config['api_key']}"}

    async def test_connection(self, config: dict) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{config['url']}/api/v1/system/status",
                    headers=self._headers(config),
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def get_sources(self, config: dict) -> list[Source]:
        return [
            Source(id="subscribes", name="Subscribes", meta={"type": "subscribes"}),
            Source(id="downloading", name="Downloading", meta={"type": "downloading"}),
        ]

    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        async with httpx.AsyncClient() as client:
            if source_id == "subscribes":
                resp = await client.get(
                    f"{config['url']}/api/v1/subscribe",
                    headers=self._headers(config),
                    timeout=10,
                )
                if resp.status_code != 200:
                    return []
                return [
                    Item(
                        id=str(s["id"]),
                        title=s.get("name", "Unknown"),
                        source_id=source_id,
                        meta={"type": s.get("type", ""), "year": s.get("year")},
                    )
                    for s in resp.json()
                ]
        return []

    async def check_updates(self, config: dict, subscriptions: list) -> list[Update]:
        updates = []
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{config['url']}/api/v1/history",
                headers=self._headers(config),
                params={"page": 1, "count": 20},
                timeout=10,
            )
            if resp.status_code == 200:
                for item in resp.json().get("list", []):
                    for sub in subscriptions:
                        if str(item.get("tmdbid")) == sub["item_id"] or item.get("title") == sub.get("item_title"):
                            updates.append(Update(
                                subscription_id=sub["id"],
                                title=f"{item.get('title', 'Unknown')} downloaded",
                                content=item.get("desc", ""),
                            ))
        return updates
```

**Step 3: 创建 __init__.py 文件**

`backend/app/plugins/komga/__init__.py`:
```python
from app.plugins.komga.plugin import KomgaPlugin
```

`backend/app/plugins/moviepilot/__init__.py`:
```python
from app.plugins.moviepilot.plugin import MoviePilotPlugin
```

**Step 4: 更新 plugins __init__.py 注册所有插件**

`backend/app/plugins/__init__.py`:
```python
from app.plugins.jellyfin.plugin import JellyfinPlugin
from app.plugins.komga.plugin import KomgaPlugin
from app.plugins.moviepilot.plugin import MoviePilotPlugin
```

**Step 5: 在 main.py 中 discover 插件**

在 lifespan 中添加：
```python
from app.core.plugin_loader import plugin_loader

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    plugin_loader.discover()
    setup_scheduler()
    yield
    scheduler.shutdown()
```

**Step 6: 运行全部后端测试**

Run: `cd backend && python -m pytest -v`
Expected: ALL PASS

**Step 7: 提交**

```bash
git add backend/app/plugins/ backend/tests/
git commit -m "feat: add Komga and MoviePilot plugins, register all plugins on startup"
```

---

<!-- PLAN_CONTINUE_7 -->

## Task 11: 前端项目初始化

**Files:**
- Create: `frontend/` (via Vite scaffold)
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/App.tsx`

**Step 1: 初始化 Vite + React + TypeScript 项目**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
```

**Step 2: 安装依赖**

```bash
npm install @tanstack/react-query react-router-dom axios
npm install -D tailwindcss @tailwindcss/vite
npx shadcn@latest init -d
```

**Step 3: 配置 Tailwind CSS**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

**Step 4: 创建 API 客户端 `frontend/src/lib/api.ts`**

```typescript
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
```

**Step 5: 安装 shadcn/ui 组件（按需）**

```bash
npx shadcn@latest add button card input label badge sidebar
npx shadcn@latest add dialog dropdown-menu separator avatar
npx shadcn@latest add table tabs toast sonner
```

**Step 6: 提交**

```bash
git add frontend/
git commit -m "feat: initialize frontend with Vite, React, Tailwind, shadcn/ui"
```

---

## Task 12: 前端布局 + 路由

**Files:**
- Create: `frontend/src/layouts/AppLayout.tsx`
- Create: `frontend/src/layouts/Sidebar.tsx`
- Create: `frontend/src/layouts/TopBar.tsx`
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: 实现 Sidebar `frontend/src/layouts/Sidebar.tsx`**

```tsx
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Rss, Container, Bell, Puzzle, Send, Users, Settings,
} from "lucide-react";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/subscriptions", label: "订阅管理", icon: Rss },
  { path: "/docker", label: "Docker 管理", icon: Container },
  { path: "/notifications", label: "通知中心", icon: Bell },
  { path: "/plugins", label: "插件管理", icon: Puzzle },
  { path: "/channels", label: "通知渠道", icon: Send },
  { path: "/users", label: "用户管理", icon: Users },
];

export function Sidebar() {
  const location = useLocation();

  return (
    <aside className="w-60 border-r bg-background flex flex-col h-screen">
      <div className="p-6">
        <h1 className="text-xl font-bold">EverySub</h1>
      </div>
      <nav className="flex-1 px-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
```

**Step 2: 实现 TopBar `frontend/src/layouts/TopBar.tsx`**

```tsx
import { Bell, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function TopBar() {
  return (
    <header className="h-14 border-b flex items-center justify-between px-6">
      <div className="flex items-center gap-2 flex-1 max-w-md">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input placeholder="Search..." className="border-0 shadow-none" />
      </div>
      <Button variant="ghost" size="icon">
        <Bell className="h-4 w-4" />
      </Button>
    </header>
  );
}
```

**Step 3: 实现 AppLayout `frontend/src/layouts/AppLayout.tsx`**

```tsx
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppLayout() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto p-6 bg-muted/30">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

**Step 4: 实现 LoginPage `frontend/src/pages/LoginPage.tsx`**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const resp = await api.post("/auth/login", { username, password });
      localStorage.setItem("token", resp.data.access_token);
      navigate("/");
    } catch {
      setError("Invalid credentials");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30">
      <Card className="w-[380px]">
        <CardHeader>
          <CardTitle className="text-center">EverySub</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full">Login</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 5: 实现 DashboardPage 占位 `frontend/src/pages/DashboardPage.tsx`**

```tsx
export function DashboardPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      <p className="text-muted-foreground">Welcome to EverySub</p>
    </div>
  );
}
```

**Step 6: 配置路由 `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "./layouts/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";

const queryClient = new QueryClient();

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

**Step 7: 验证前端启动**

Run: `cd frontend && npm run build`
Expected: Build succeeds without errors

**Step 8: 提交**

```bash
git add frontend/
git commit -m "feat: add frontend layout with sidebar, topbar, login, and routing"
```

---

<!-- PLAN_CONTINUE_8 -->

## Task 13: 前端核心页面 (插件管理 + 订阅管理)

**Files:**
- Create: `frontend/src/hooks/useAuth.ts`
- Create: `frontend/src/hooks/usePlugins.ts`
- Create: `frontend/src/hooks/useSubscriptions.ts`
- Create: `frontend/src/pages/PluginsPage.tsx`
- Create: `frontend/src/pages/SubscriptionsPage.tsx`
- Modify: `frontend/src/App.tsx` (add routes)

**Step 1: 创建 API hooks**

`frontend/src/hooks/usePlugins.ts`:
```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface PluginInfo {
  name: string;
  display_name: string;
  version: string;
  description: string;
  config_schema: Record<string, unknown>;
}

export interface PluginInstance {
  id: number;
  plugin_name: string;
  display_name: string;
  config: Record<string, unknown>;
  docker_id: string | null;
  enabled: boolean;
}

export function useAvailablePlugins() {
  return useQuery<PluginInfo[]>({
    queryKey: ["plugins", "available"],
    queryFn: () => api.get("/plugins/available").then((r) => r.data),
  });
}

export function usePluginInstances() {
  return useQuery<PluginInstance[]>({
    queryKey: ["plugins", "instances"],
    queryFn: () => api.get("/plugins/instances").then((r) => r.data),
  });
}

export function useCreateInstance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { plugin_name: string; display_name: string; config: Record<string, unknown> }) =>
      api.post("/plugins/instances", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plugins", "instances"] }),
  });
}

export function useDeleteInstance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/plugins/instances/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plugins", "instances"] }),
  });
}
```

`frontend/src/hooks/useSubscriptions.ts`:
```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface Subscription {
  id: number;
  user_id: number;
  instance_id: number;
  item_id: string;
  item_title: string;
  item_meta: Record<string, unknown>;
  status: string;
  last_checked: string | null;
  created_at: string;
}

export function useSubscriptions() {
  return useQuery<Subscription[]>({
    queryKey: ["subscriptions"],
    queryFn: () => api.get("/subscriptions").then((r) => r.data),
  });
}

export function useCreateSubscription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { instance_id: number; item_id: string; item_title: string; item_meta: Record<string, unknown> }) =>
      api.post("/subscriptions", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });
}

export function useDeleteSubscription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/subscriptions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });
}
```

**Step 2: 实现 PluginsPage**

`frontend/src/pages/PluginsPage.tsx`:
```tsx
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Trash2 } from "lucide-react";
import { useAvailablePlugins, usePluginInstances, useCreateInstance, useDeleteInstance } from "@/hooks/usePlugins";

export function PluginsPage() {
  const { data: available = [] } = useAvailablePlugins();
  const { data: instances = [] } = usePluginInstances();
  const createInstance = useCreateInstance();
  const deleteInstance = useDeleteInstance();
  const [selectedPlugin, setSelectedPlugin] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [displayName, setDisplayName] = useState("");

  const handleCreate = () => {
    if (!selectedPlugin) return;
    createInstance.mutate({
      plugin_name: selectedPlugin,
      display_name: displayName,
      config: formData,
    });
    setSelectedPlugin(null);
    setFormData({});
    setDisplayName("");
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">插件管理</h2>
        <Dialog>
          <DialogTrigger asChild>
            <Button><Plus className="h-4 w-4 mr-2" />添加实例</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>添加插件实例</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>选择插件</Label>
                <div className="flex gap-2 flex-wrap">
                  {available.map((p) => (
                    <Badge
                      key={p.name}
                      variant={selectedPlugin === p.name ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => setSelectedPlugin(p.name)}
                    >
                      {p.display_name}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label>显示名称</Label>
                <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="My Jellyfin" />
              </div>
              {selectedPlugin && available.find((p) => p.name === selectedPlugin)?.config_schema && (
                <div className="space-y-2">
                  {Object.entries(
                    (available.find((p) => p.name === selectedPlugin)?.config_schema as any)?.properties || {}
                  ).map(([key, schema]: [string, any]) => (
                    <div key={key} className="space-y-1">
                      <Label>{schema.title || key}</Label>
                      <Input
                        value={formData[key] || ""}
                        onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
                      />
                    </div>
                  ))}
                </div>
              )}
              <Button onClick={handleCreate} className="w-full">创建</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {instances.map((inst) => (
          <Card key={inst.id} className="rounded-xl">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">{inst.display_name}</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => deleteInstance.mutate(inst.id)}>
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </CardHeader>
            <CardContent>
              <Badge variant="secondary">{inst.plugin_name}</Badge>
              <Badge variant={inst.enabled ? "default" : "outline"} className="ml-2">
                {inst.enabled ? "Active" : "Disabled"}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

**Step 3: 实现 SubscriptionsPage**

`frontend/src/pages/SubscriptionsPage.tsx`:
```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Trash2 } from "lucide-react";
import { useSubscriptions, useDeleteSubscription } from "@/hooks/useSubscriptions";

export function SubscriptionsPage() {
  const { data: subscriptions = [] } = useSubscriptions();
  const deleteSub = useDeleteSubscription();

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">订阅管理</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {subscriptions.map((sub) => (
          <Card key={sub.id} className="rounded-xl">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">{sub.item_title}</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => deleteSub.mutate(sub.id)}>
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </CardHeader>
            <CardContent>
              <Badge variant={sub.status === "active" ? "default" : "secondary"}>
                {sub.status}
              </Badge>
              {sub.last_checked && (
                <span className="text-xs text-muted-foreground ml-2">
                  Last checked: {new Date(sub.last_checked).toLocaleString()}
                </span>
              )}
            </CardContent>
          </Card>
        ))}
        {subscriptions.length === 0 && (
          <p className="text-muted-foreground col-span-full text-center py-12">
            No subscriptions yet. Add a plugin instance first, then subscribe to content.
          </p>
        )}
      </div>
    </div>
  );
}
```

**Step 4: 添加路由到 App.tsx**

在 AppLayout 的 Routes 中添加：
```tsx
import { PluginsPage } from "./pages/PluginsPage";
import { SubscriptionsPage } from "./pages/SubscriptionsPage";

// Inside Routes:
<Route path="/plugins" element={<PluginsPage />} />
<Route path="/subscriptions" element={<SubscriptionsPage />} />
```

**Step 5: 验证构建**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 6: 提交**

```bash
git add frontend/
git commit -m "feat: add plugins and subscriptions pages with TanStack Query hooks"
```

---

## Task 14: 前端剩余页面 (Docker + 通知 + Dashboard)

**Files:**
- Create: `frontend/src/hooks/useDocker.ts`
- Create: `frontend/src/hooks/useNotifications.ts`
- Create: `frontend/src/pages/DockerPage.tsx`
- Create: `frontend/src/pages/NotificationsPage.tsx`
- Create: `frontend/src/pages/ChannelsPage.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx`

实现方式与 Task 13 类似：创建 hooks → 实现页面组件 → 注册路由。

Dashboard 页面实现看板式布局，按状态分列展示订阅卡片，使用参考图的柔和渐变色风格。

**Step 1-5:** 按照 Task 13 的模式实现各页面

**Step 6: 验证构建**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 7: 提交**

```bash
git add frontend/
git commit -m "feat: add Docker, notifications, channels, and dashboard pages"
```

---

## Task 15: Docker 部署配置

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

**Step 1: 创建后端 Dockerfile `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: 创建前端 Dockerfile `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

`frontend/nginx.conf`:
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**Step 3: 创建 docker-compose.yml**

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
    env_file:
      - .env
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: unless-stopped
```

**Step 4: 创建 .env.example**

```env
DATABASE_URL=sqlite+aiosqlite:///./data/everysub.db
SECRET_KEY=change-me-to-a-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

**Step 5: 验证 Docker 构建**

Run: `docker compose build`
Expected: Both images build successfully

**Step 6: 提交**

```bash
git add backend/Dockerfile frontend/Dockerfile frontend/nginx.conf docker-compose.yml .env.example
git commit -m "feat: add Docker deployment configuration"
```

---

## Task 16: Alembic 数据库迁移

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/` (via alembic init)

**Step 1: 初始化 Alembic**

```bash
cd backend
alembic init alembic
```

**Step 2: 配置 alembic env.py 使用 async engine**

修改 `backend/alembic/env.py` 使用项目的 database 配置和 async engine。

**Step 3: 生成初始迁移**

```bash
alembic revision --autogenerate -m "initial schema"
```

**Step 4: 运行迁移验证**

```bash
alembic upgrade head
```

**Step 5: 提交**

```bash
git add backend/alembic/ backend/alembic.ini
git commit -m "feat: add Alembic database migrations"
```

---

## 总结

| Task | 内容 | 依赖 |
|------|------|------|
| 1 | 后端骨架 + 数据库基础 | - |
| 2 | 数据模型 | Task 1 |
| 3 | 用户认证 (JWT) | Task 2 |
| 4 | 插件系统核心 | Task 1 |
| 5 | 插件管理 + 订阅 API | Task 3, 4 |
| 6 | 通知系统 | Task 3 |
| 7 | Docker 管理模块 | Task 3 |
| 8 | 定时调度器 | Task 4, 5, 6 |
| 9 | Jellyfin 插件 | Task 4 |
| 10 | Komga + MoviePilot 插件 | Task 4 |
| 11 | 前端项目初始化 | - |
| 12 | 前端布局 + 路由 | Task 11 |
| 13 | 前端核心页面 | Task 12 |
| 14 | 前端剩余页面 | Task 13 |
| 15 | Docker 部署配置 | Task 10, 14 |
| 16 | Alembic 迁移 | Task 2 |

**可并行的任务组：**
- Task 1 + Task 11（后端骨架 + 前端初始化）
- Task 4 + Task 6 + Task 7（插件核心 + 通知 + Docker，都依赖 Task 3）
- Task 9 + Task 10（各插件实现，都依赖 Task 4）
- Task 13 + Task 14（前端页面，可部分并行）
