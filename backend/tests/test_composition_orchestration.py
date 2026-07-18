"""自动化组合模板部署相关测试。"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.database import Base
from app.models.app_store import App
from app.models.orchestration import (
    AppInstance,
    AppOrchestration,
    AppOrchestrationInstance,
)
from app.services.app_store import app_service
from app.services.orchestration import orchestration_service


@pytest_asyncio.fixture(name="db")
async def _db():
    """提供内存 SQLite 会话。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def media_orchestration(db):
    """创建一个影视组合模板。"""
    orchestration = AppOrchestration(
        name="media-stack",
        display_name="影视媒体栈",
        category="media",
        app_composition=[
            {"app_name": "moviepilot", "relation": "required"},
            {"app_name": "qbittorrent", "relation": "required"},
            {"app_name": "jellyfin", "relation": "optional", "group": "player"},
            {"app_name": "emby", "relation": "optional", "group": "player"},
        ],
        shared_config_schema={
            "type": "object",
            "properties": {
                "volumes": {
                    "type": "array",
                    "default": [
                        {"mode": "rw", "host_path": "media", "container_path": "/media"},
                        {"mode": "rw", "host_path": "downloads", "container_path": "/downloads"},
                    ],
                    "items": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["rw", "ro"], "default": "rw"},
                            "host_path": {"type": "string", "format": "directory"},
                            "container_path": {"type": "string"},
                        },
                        "required": ["host_path", "container_path", "mode"],
                    },
                },
                "env": {
                    "type": "array",
                    "default": [
                        {"key": "TZ", "value": "Asia/Shanghai"},
                    ],
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"},
                        },
                        "required": ["key", "value"],
                    },
                },
            },
            "required": ["volumes", "env"],
            "containers": [
                {
                    "name": "shared",
                    "title": "公共配置",
                    "description": "所有影视自动化应用共享的存储空间和环境变量",
                    "settings": [
                        {"type": "volumes", "title": "存储空间设置", "fields": ["volumes"]},
                        {"type": "env", "title": "环境变量", "fields": ["env"]},
                    ],
                }
            ],
        },
    )
    db.add(orchestration)
    await db.commit()
    await db.refresh(orchestration)
    return orchestration


@pytest_asyncio.fixture
async def media_apps(db):
    """创建影视相关应用。"""
    apps = [
        App(
            name="moviepilot",
            display_name="MoviePilot",
            yaml_template="services:\n  app:\n    image: moviepilot:latest",
        ),
        App(
            name="qbittorrent",
            display_name="qBittorrent",
            yaml_template="services:\n  app:\n    image: qbittorrent:latest",
        ),
        App(
            name="jellyfin",
            display_name="Jellyfin",
            yaml_template="services:\n  app:\n    image: jellyfin:latest",
        ),
        App(
            name="emby",
            display_name="Emby",
            yaml_template="services:\n  app:\n    image: emby:latest",
        ),
    ]
    for app in apps:
        db.add(app)
    await db.commit()
    return apps


@pytest.mark.asyncio
async def test_deploy_composition_missing_required_raises(db, media_apps, media_orchestration):
    """必选应用未选时应抛出异常。"""
    with pytest.raises(Exception) as exc_info:
        await orchestration_service.deploy(
            db,
            orchestration_name="media-stack",
            instance_name="test-stack",
            selected_apps=["jellyfin"],
            app_configs={},
            shared_config={},
        )
    assert "必选应用" in str(exc_info.value)


@pytest.mark.asyncio
async def test_deploy_composition_conflicting_raises(db, media_apps, media_orchestration):
    """互斥应用同时选时应抛出异常。"""
    # 将 jellyfin 和 emby 设为互斥
    media_orchestration.app_composition = [
        {"app_name": "moviepilot", "relation": "required"},
        {"app_name": "qbittorrent", "relation": "required"},
        {"app_name": "jellyfin", "relation": "optional", "conflict_with": ["emby"]},
        {"app_name": "emby", "relation": "optional", "conflict_with": ["jellyfin"]},
    ]
    await db.commit()

    with pytest.raises(Exception) as exc_info:
        await orchestration_service.deploy(
            db,
            orchestration_name="media-stack",
            instance_name="test-stack",
            selected_apps=["moviepilot", "qbittorrent", "jellyfin", "emby"],
            app_configs={},
            shared_config={},
        )
    assert "互斥" in str(exc_info.value)


@pytest.mark.asyncio
async def test_deploy_composition_success(db, media_apps, media_orchestration, monkeypatch):
    """正常选择时应创建组合部署记录并返回任务 ID。"""

    async def fake_deploy(db, app_name, instance_name, config, user_id=None):
        # 创建应用实例记录以模拟 AppService.deploy 行为
        app_result = await db.execute(select(App).where(App.name == app_name))
        app = app_result.scalar_one()
        instance = AppInstance(
            app_id=app.id,
            instance_name=instance_name,
            config=config,
            status="running",
        )
        db.add(instance)
        await db.commit()
        await db.refresh(instance)
        return instance, f"task-{app_name}"

    monkeypatch.setattr(app_service, "deploy", fake_deploy)

    group, returned_task_ids = await orchestration_service.deploy(
        db,
        orchestration_name="media-stack",
        instance_name="test-stack",
        selected_apps=["moviepilot", "qbittorrent", "jellyfin"],
        app_configs={
            "moviepilot": {"port": 3000},
            "qbittorrent": {"port": 8080},
            "jellyfin": {"port": 8096},
        },
        shared_config={"media_root": "media", "downloads_root": "downloads"},
        user_id=1,
    )

    assert group is not None
    assert group.instance_name == "test-stack"
    assert len(returned_task_ids) == 3

    # 验证组合部署记录已创建
    result = await db.execute(
        select(AppOrchestrationInstance).where(
            AppOrchestrationInstance.id == group.id
        )
    )
    stored_group = result.scalar_one()
    assert stored_group.status == "running"

    # 验证关联实例已创建
    result = await db.execute(
        select(AppInstance).where(
            AppInstance.orchestration_group_id == group.id
        )
    )
    instances = result.scalars().all()
    assert len(instances) == 3
    instance_names = {i.instance_name for i in instances}
    assert instance_names == {
        "test-stack-moviepilot",
        "test-stack-qbittorrent",
        "test-stack-jellyfin",
    }
