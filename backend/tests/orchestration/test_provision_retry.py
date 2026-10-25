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
from app.services.apps import ProvisionResult
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


@pytest.mark.asyncio
async def test_write_provision_result_keeps_credentials_on_failure(session_local):
    """配置失败时也保留账号密码，保证「重新装配」能用同一套凭据重试。"""
    group_id = await _seed_group(session_local)

    await orchestration_service._write_provision_result(
        group_id,
        "moviepilot",
        {"username": "admin", "password": "unified-pass", "api_key": "mp-token"},
        None,
        "服务未就绪",
    )

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)

    entry = group.app_configs["moviepilot"]
    assert entry["username"] == "admin"
    assert entry["password"] == "unified-pass"
    assert entry["api_key"] == "mp-token"
    assert entry["provision_error"] == "服务未就绪"
    assert "provisioned" not in entry


@pytest.mark.asyncio
async def test_write_provision_result_keeps_previous_password_on_failure(session_local):
    """失败时不能用目标密码覆盖旧密码，否则下次重试就无法登录改密。"""
    group_id = await _seed_group(session_local)

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)
        configs = dict(group.app_configs)
        configs["moviepilot"] = {
            **configs["moviepilot"],
            "username": "admin",
            "password": "old-pass",
        }
        group.app_configs = configs
        await db.commit()

    await orchestration_service._write_provision_result(
        group_id,
        "moviepilot",
        {"username": "admin", "password": "unified-pass"},
        None,
        "服务未就绪",
    )

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)

    entry = group.app_configs["moviepilot"]
    assert entry["password"] == "old-pass"
    assert entry["provision_error"] == "服务未就绪"


@pytest.mark.asyncio
async def test_persist_pending_credentials_keeps_previous_password(session_local):
    """部署前落库凭据时也不能覆盖尚未生效的旧密码。"""
    group_id = await _seed_group(session_local)

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)
        configs = dict(group.app_configs)
        configs["moviepilot"] = {
            **configs["moviepilot"],
            "username": "admin",
            "password": "old-pass",
        }
        group.app_configs = configs
        await db.commit()

    await orchestration_service._persist_pending_credentials(
        group_id,
        [
            {
                "app_name": "moviepilot",
                "credentials": {"username": "admin", "password": "unified-pass"},
            }
        ],
    )

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)

    entry = group.app_configs["moviepilot"]
    assert entry["password"] == "old-pass"
    assert entry["username"] == "admin"


@pytest.mark.asyncio
async def test_reprovision_uses_stored_password_as_previous(session_local):
    """保留的旧密码要作为 previous_password 传给重试流程。"""
    group_id = await _seed_group(session_local)

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)
        configs = dict(group.app_configs)
        configs["moviepilot"] = {
            **configs["moviepilot"],
            "username": "admin",
            "password": "old-pass",
        }
        group.app_configs = configs
        await db.commit()

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
    assert creds["password"] == "unified-pass"
    assert creds["previous_password"] == "old-pass"


@pytest.mark.asyncio
async def test_write_provision_result_keeps_explicit_apikey_auth_type(session_local):
    """自动配置成功不应把用户选择的 API Key 认证方式改成账号密码。"""
    group_id = await _seed_group(session_local)

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)
        configs = dict(group.app_configs)
        configs["moviepilot"] = {
            **configs["moviepilot"],
            "auth_type": "apikey",
            "api_key": "user-key",
        }
        group.app_configs = configs
        await db.commit()

    await orchestration_service._write_provision_result(
        group_id,
        "moviepilot",
        {"username": "admin", "password": "unified-pass"},
        ProvisionResult(ok=True, message="配置成功", username="admin"),
        "配置成功",
    )

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)

    entry = group.app_configs["moviepilot"]
    assert entry["auth_type"] == "apikey"
    assert entry["api_key"] == "user-key"
    assert entry["username"] == "admin"
    assert entry["provisioned"] is True


@pytest.mark.asyncio
async def test_persist_pending_credentials_keeps_explicit_apikey_auth_type(
    session_local,
):
    """落库待配置凭据时同样不改动用户选择的 API Key 认证方式。"""
    group_id = await _seed_group(session_local)

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)
        configs = dict(group.app_configs)
        configs["moviepilot"] = {
            **configs["moviepilot"],
            "auth_type": "apikey",
            "api_key": "user-key",
        }
        group.app_configs = configs
        await db.commit()

    await orchestration_service._persist_pending_credentials(
        group_id,
        [
            {
                "app_name": "moviepilot",
                "credentials": {"username": "admin", "password": "unified-pass"},
            },
            {
                "app_name": "qbittorrent",
                "credentials": {"username": "admin", "password": "unified-pass"},
            },
        ],
    )

    async with session_local() as db:
        group = await orchestration_service.get_group(db, group_id)

    entry = group.app_configs["moviepilot"]
    assert entry["auth_type"] == "apikey"
    assert entry["api_key"] == "user-key"
    assert entry["username"] == "admin"

    # 未配置过认证方式的应用仍补齐为账号密码
    entry = group.app_configs["qbittorrent"]
    assert entry["auth_type"] == "basic"


@pytest.mark.asyncio
async def test_reprovision_generates_password_for_url_only_app(session_local):
    """旧实例只有访问地址时，补配置生成密码而不是直接跳过。"""
    async with session_local() as db:
        db.add(
            SystemConfig(
                id=1,
                default_admin_username="admin",
                default_admin_password="",
            )
        )
        orch = AppOrchestration(
            name="music-auto",
            display_name="音乐自动化",
            category="music",
            app_composition=[],
            shared_config_schema={},
        )
        db.add(orch)
        await db.flush()
        group = AppOrchestrationInstance(
            orchestration_id=orch.id,
            instance_name="music-auto",
            status="running",
            app_configs={"music-dl": {"url": "http://host:10000"}},
        )
        db.add(group)
        await db.flush()
        app = App(
            name="music-dl",
            display_name="music-dl",
            yaml_template="services: {}",
        )
        db.add(app)
        await db.flush()
        db.add(
            AppInstance(
                orchestration_group_id=group.id,
                app_id=app.id,
                instance_name="music-auto-music-dl",
                config={},
            )
        )
        await db.commit()
        group_id = group.id

    with patch.object(
        orchestration_service,
        "_provision_app",
        new=AsyncMock(return_value=None),
    ) as provision:
        await orchestration_service._reprovision_pending(group_id)

    assert provision.await_count == 1
    call = provision.await_args_list[0]
    assert call.args[1] == "music-dl"
    assert call.args[2]["username"] == "admin"
    assert call.args[2]["password"]


@pytest.mark.asyncio
async def test_reprovision_reader_env_spec_without_api_token(session_local):
    """Reader env 规格没有 API Token 时，补配置不应读取缺失的键。"""
    async with session_local() as db:
        orch = AppOrchestration(
            name="book-auto",
            display_name="书籍自动化",
            category="books",
            app_composition=[],
            shared_config_schema={},
        )
        db.add(orch)
        await db.flush()
        group = AppOrchestrationInstance(
            orchestration_id=orch.id,
            instance_name="book-auto",
            status="running",
            app_configs={
                "reader": {
                    "url": "http://host:9013",
                    "username": "admin",
                    "password": "reader-pass",
                }
            },
        )
        db.add(group)
        await db.flush()
        app = App(
            name="reader",
            display_name="reader",
            yaml_template="services: {}",
        )
        db.add(app)
        await db.flush()
        db.add(
            AppInstance(
                orchestration_group_id=group.id,
                app_id=app.id,
                instance_name="book-auto-reader",
                config={
                    "reader_env": [
                        {"key": "READER_APP_SECURE", "value": "true"}
                    ]
                },
            )
        )
        await db.commit()
        group_id = group.id

    with patch.object(
        orchestration_service,
        "_provision_app",
        new=AsyncMock(return_value=ProvisionResult(ok=True)),
    ) as provision:
        await orchestration_service._reprovision_pending(group_id)

    assert provision.await_count == 1
    call = provision.await_args_list[0]
    assert call.args[1] == "reader"
    assert call.args[2]["username"] == "admin"
    assert call.args[2]["password"] == "reader-pass"
    assert not call.args[2].get("api_key")
