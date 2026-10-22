"""手动重新装配前的账号补配置（reprovision）测试。"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 — 注册所有模型到 Base.metadata
from app.database import Base
from app.models.app_store import App
from app.models.orchestration import (
    AppInstance,
    AppOrchestration,
    AppOrchestrationInstance,
)
from app.models.system_config import SystemConfig
from app.services.orchestration import orchestration_service


@pytest_asyncio.fixture(name="session_local")
async def _session_local(monkeypatch):
    """提供内存 SQLite 会话工厂，并接管 provisioning 模块的数据库会话。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(
        "app.services.orchestration.provisioning.async_session", SessionLocal
    )
    yield SessionLocal
    await engine.dispose()


async def _seed_group(session_local) -> int:
    """写入未完成账号配置的影视实例组，返回组 ID。"""
    async with session_local() as db:
        db.add(
            SystemConfig(
                id=1,
                default_admin_username="admin",
                default_admin_password="unified-pass",
            )
        )
        orch = AppOrchestration(
            name="media-stack",
            display_name="影视自动化",
            category="media",
            app_composition=[],
            shared_config_schema={},
        )
        db.add(orch)
        await db.flush()
        group = AppOrchestrationInstance(
            orchestration_id=orch.id,
            instance_name="movie-auto",
            status="running",
            app_configs={
                "moviepilot": {"url": "http://host:3000"},
                "qbittorrent": {"url": "http://host:8081"},
                "jellyfin": {
                    "url": "http://host:8096",
                    "provisioned": True,
                },
            },
        )
        db.add(group)
        await db.flush()
        for name in ("moviepilot", "qbittorrent", "jellyfin"):
            app = App(
                name=name,
                display_name=name,
                yaml_template="services: {}",
            )
            db.add(app)
            await db.flush()
            config = {}
            if name == "moviepilot":
                config = {
                    "moviepilot_env": [
                        {"key": "API_TOKEN", "value": "mp-token"}
                    ]
                }
            db.add(
                AppInstance(
                    orchestration_group_id=group.id,
                    app_id=app.id,
                    instance_name=f"movie-auto-{name}",
                    config=config,
                )
            )
        await db.commit()
        return group.id


@pytest.mark.asyncio
async def test_reprovision_unprovisioned_apps_only(session_local):
    """只补做未配置成功的应用，已配置的跳过。"""
    group_id = await _seed_group(session_local)

    with patch.object(
        orchestration_service,
        "_provision_app",
        new=AsyncMock(return_value=None),
    ) as provision:
        await orchestration_service._reprovision_pending(group_id)

    names = [call.args[1] for call in provision.await_args_list]
    assert names == ["moviepilot", "qbittorrent"]


@pytest.mark.asyncio
async def test_reprovision_reuses_unified_password_and_env_api_token(session_local):
    """补配置使用统一密码，并沿用部署配置中的 MoviePilot API Token。"""
    group_id = await _seed_group(session_local)

    with patch.object(
        orchestration_service,
        "_provision_app",
        new=AsyncMock(return_value=None),
    ) as provision:
        await orchestration_service._reprovision_pending(group_id)

    moviepilot_call = next(
        call for call in provision.await_args_list if call.args[1] == "moviepilot"
    )
    creds = moviepilot_call.args[2]
    assert creds["username"] == "admin"
    assert creds["password"] == "unified-pass"
    assert creds["api_key"] == "mp-token"
    assert moviepilot_call.args[4] == "movie-auto-moviepilot"
