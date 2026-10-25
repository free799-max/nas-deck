"""编排实例组重新部署（redeploy）相关测试。"""

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.database import Base
from app.models.app_store import App
from app.models.docker import DockerComposeProject
from app.models.orchestration import (
    AppInstance,
    AppOrchestration,
    AppOrchestrationInstance,
    OrchestrationUpdateEvent,
)
from app.services.app_store import app_service
from app.services.compose.compose_service import compose_manager
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
async def orchestration(db):
    """创建一个简单的编排模板。"""
    item = AppOrchestration(
        name="media-stack",
        display_name="影视媒体栈",
        category="media",
        app_composition=[
            {"app_name": "moviepilot", "relation": "required"},
            {"app_name": "jellyfin", "relation": "optional"},
        ],
        shared_config_schema={},
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@pytest_asyncio.fixture
async def apps(db):
    """创建编排涉及的应用。"""
    items = [
        App(
            name="moviepilot",
            display_name="MoviePilot",
            yaml_template="services:\n  app:\n    image: moviepilot:latest",
        ),
        App(
            name="jellyfin",
            display_name="Jellyfin",
            yaml_template="services:\n  app:\n    image: jellyfin:latest",
        ),
    ]
    for item in items:
        db.add(item)
    await db.commit()
    return items


@pytest_asyncio.fixture
async def failed_group(db, orchestration, apps):
    """模拟一个部署失败的实例组：moviepilot 实例 error 且关联了已创建的项目。"""
    group = AppOrchestrationInstance(
        orchestration_id=orchestration.id,
        instance_name="test-stack",
        shared_config={"env": [{"key": "TZ", "value": "Asia/Shanghai"}]},
        status="error",
    )
    db.add(group)
    await db.flush()

    project = DockerComposeProject(
        project_name="test-stack-moviepilot",
        config_files='["/tmp/compose.yaml"]',
        working_dir="/tmp",
    )
    db.add(project)
    await db.flush()

    app_by_name = {a.name: a for a in apps}
    old_instance = AppInstance(
        app_id=app_by_name["moviepilot"].id,
        orchestration_id=orchestration.id,
        orchestration_group_id=group.id,
        instance_name="test-stack-moviepilot",
        config={"port": 3000},
        status="error",
        project_id=project.id,
    )
    db.add(old_instance)
    await db.commit()
    return group


def _make_fake_deploy(db, created: list[str]):
    """模拟 app_service.deploy：创建 running 实例并返回任务 ID。"""

    async def fake_deploy(db, app_name, instance_name, config, user_id=None):
        app_result = await db.execute(select(App).where(App.name == app_name))
        app = app_result.scalar_one()
        instance = AppInstance(
            app_id=app.id,
            instance_name=instance_name,
            config=config,
            status="deploying",
        )
        db.add(instance)
        await db.commit()
        await db.refresh(instance)
        created.append(app_name)
        return instance, f"task-{app_name}"

    return fake_deploy


def _make_fake_delete_project(db, deleted: list[str]):
    """模拟 compose_manager.delete_project：级联删除实例行并删除项目。"""

    async def fake_delete_project(db, project):
        deleted.append(project.project_name)
        await db.execute(
            delete(AppInstance).where(AppInstance.project_id == project.id)
        )
        await db.delete(project)
        await db.commit()

    return fake_delete_project


@pytest.mark.asyncio
async def test_redeploy_cleans_old_instance_and_project(
    db, apps, orchestration, failed_group, monkeypatch
):
    """重新部署应清理旧实例与其关联项目，并在原组上重建实例、返回任务 ID。"""
    deleted: list[str] = []
    created: list[str] = []
    monkeypatch.setattr(
        compose_manager, "delete_project", _make_fake_delete_project(db, deleted)
    )
    monkeypatch.setattr(app_service, "deploy", _make_fake_deploy(db, created))

    group, task_ids = await orchestration_service.redeploy_instance(
        db,
        group_id=failed_group.id,
        instance_name="test-stack",
        selected_apps=["moviepilot"],
        app_configs={"moviepilot": {"port": 3000}},
        shared_config={"env": [{"key": "TZ", "value": "Asia/Shanghai"}]},
        user_id=1,
    )

    assert deleted == ["test-stack-moviepilot"]
    assert created == ["moviepilot"]
    # 应用部署任务 + 自动配置/装配进度跟踪任务
    assert task_ids[0] == "task-moviepilot"
    assert len(task_ids) == 2
    assert group.id == failed_group.id
    assert group.status == "running"

    # 旧实例已删除，组内只剩新建实例
    result = await db.execute(
        select(AppInstance).where(
            AppInstance.orchestration_group_id == failed_group.id
        )
    )
    instances = result.scalars().all()
    assert len(instances) == 1
    assert instances[0].instance_name == "test-stack-moviepilot"
    assert instances[0].status == "deploying"

    # 旧项目已删除，同名项目可重新创建（不再 409）
    result = await db.execute(
        select(DockerComposeProject).where(
            DockerComposeProject.project_name == "test-stack-moviepilot"
        )
    )
    assert result.scalar_one_or_none() is None

    # 版本快照同步到模板当前版本，并记录一条 instance 更新事件
    assert group.orchestration_version == orchestration.version
    events = (
        await db.execute(
            select(OrchestrationUpdateEvent).where(
                OrchestrationUpdateEvent.group_id == failed_group.id
            )
        )
    ).scalars().all()
    assert len(events) == 1
    event = events[0]
    assert event.scope == "instance"
    assert event.mode == "manual"
    assert event.status == "applied"
    assert event.from_version is None
    assert event.to_version == orchestration.version
    assert event.detail == {"selected_apps": ["moviepilot"]}


@pytest.mark.asyncio
async def test_redeploy_optional_app_without_required(
    db, apps, orchestration, failed_group, monkeypatch
):
    """修复时可只重部署部分应用，不要求再次选中必选应用。"""
    created: list[str] = []
    monkeypatch.setattr(app_service, "deploy", _make_fake_deploy(db, created))

    group, task_ids = await orchestration_service.redeploy_instance(
        db,
        group_id=failed_group.id,
        instance_name="test-stack",
        selected_apps=["jellyfin"],
        app_configs={"jellyfin": {"port": 8096}},
        shared_config={"env": [{"key": "TZ", "value": "Asia/Shanghai"}]},
        user_id=1,
    )

    assert created == ["jellyfin"]
    assert task_ids[0] == "task-jellyfin"

    # 未选中的必选应用保持原状
    result = await db.execute(
        select(AppInstance).where(
            AppInstance.orchestration_group_id == failed_group.id,
            AppInstance.instance_name == "test-stack-moviepilot",
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_redeploy_fallback_project_lookup_when_project_id_missing(
    db, apps, orchestration, failed_group, monkeypatch
):
    """实例 project_id 为空时，应按项目名规则兜底删除残留的 Compose 项目。"""
    # 模拟重启丢失部署协程的场景：实例卡在 deploying 且无 project_id，
    # 但同名项目残留在数据库中
    app_by_name = {a.name: a for a in apps}
    dangling_instance = AppInstance(
        app_id=app_by_name["jellyfin"].id,
        orchestration_id=orchestration.id,
        orchestration_group_id=failed_group.id,
        instance_name="test-stack-jellyfin",
        config={},
        status="deploying",
        project_id=None,
    )
    db.add(dangling_instance)
    dangling_project = DockerComposeProject(
        project_name="test-stack-jellyfin",
        config_files='["/tmp/compose.yaml"]',
        working_dir="/tmp",
    )
    db.add(dangling_project)
    await db.commit()

    deleted: list[str] = []
    created: list[str] = []
    monkeypatch.setattr(
        compose_manager, "delete_project", _make_fake_delete_project(db, deleted)
    )
    monkeypatch.setattr(app_service, "deploy", _make_fake_deploy(db, created))

    group, task_ids = await orchestration_service.redeploy_instance(
        db,
        group_id=failed_group.id,
        instance_name="test-stack",
        selected_apps=["moviepilot", "jellyfin"],
        app_configs={"moviepilot": {"port": 3000}, "jellyfin": {"port": 8096}},
        shared_config={},
    )

    assert set(deleted) == {"test-stack-moviepilot", "test-stack-jellyfin"}
    assert set(created) == {"moviepilot", "jellyfin"}
    assert task_ids[:2] == ["task-moviepilot", "task-jellyfin"]
    assert len(task_ids) == 3
    assert group.status == "running"

    # 残留实例行与项目都被清理
    result = await db.execute(
        select(AppInstance).where(
            AppInstance.orchestration_group_id == failed_group.id
        )
    )
    instances = result.scalars().all()
    assert len(instances) == 2
    assert all(i.status == "deploying" for i in instances)


@pytest.mark.asyncio
async def test_redeploy_removes_instance_row_without_any_project(
    db, apps, orchestration, failed_group, monkeypatch
):
    """实例既无 project_id 也无同名项目时，仍应删除残留实例行。"""
    app_by_name = {a.name: a for a in apps}
    orphan_instance = AppInstance(
        app_id=app_by_name["jellyfin"].id,
        orchestration_id=orchestration.id,
        orchestration_group_id=failed_group.id,
        instance_name="test-stack-jellyfin",
        config={},
        status="error",
        project_id=None,
    )
    db.add(orphan_instance)
    await db.commit()

    deleted: list[str] = []
    created: list[str] = []
    monkeypatch.setattr(
        compose_manager, "delete_project", _make_fake_delete_project(db, deleted)
    )
    monkeypatch.setattr(app_service, "deploy", _make_fake_deploy(db, created))

    group, task_ids = await orchestration_service.redeploy_instance(
        db,
        group_id=failed_group.id,
        instance_name="test-stack",
        selected_apps=["moviepilot", "jellyfin"],
        app_configs={},
        shared_config={},
    )

    assert deleted == ["test-stack-moviepilot"]
    assert task_ids[:2] == ["task-moviepilot", "task-jellyfin"]
    assert len(task_ids) == 3
    assert group.status == "running"

    result = await db.execute(
        select(AppInstance).where(
            AppInstance.orchestration_group_id == failed_group.id
        )
    )
    instances = result.scalars().all()
    assert len(instances) == 2


@pytest.mark.asyncio
async def test_redeploy_cleanup_failure_aborts(
    db, apps, orchestration, failed_group, monkeypatch
):
    """清理旧项目失败时应报错且不进入重建阶段。"""
    created: list[str] = []

    async def failing_delete_project(db, project):
        raise RuntimeError("docker compose down 失败")

    monkeypatch.setattr(compose_manager, "delete_project", failing_delete_project)
    monkeypatch.setattr(app_service, "deploy", _make_fake_deploy(db, created))

    with pytest.raises(Exception) as exc_info:
        await orchestration_service.redeploy_instance(
            db,
            group_id=failed_group.id,
            instance_name="test-stack",
            selected_apps=["moviepilot"],
            app_configs={},
            shared_config={},
        )
    assert "清理旧部署失败" in str(exc_info.value)

    # 未创建任何新实例/任务
    assert created == []


@pytest.mark.asyncio
async def test_redeploy_rejected_while_deploy_in_flight(
    db, apps, orchestration, failed_group, monkeypatch
):
    """组内实例有正在进行的部署任务时，修复应被拒绝且不做任何清理。"""
    from app.core.exceptions import APIException
    from app.services.orchestration.deploy_task_service import deploy_task_manager

    result = await db.execute(
        select(AppInstance).where(
            AppInstance.orchestration_group_id == failed_group.id
        )
    )
    old_instance = result.scalars().one()

    # 制造一个进行中的部署任务，占用该实例
    task_id = deploy_task_manager.create_task(
        "app_deploy", instance_id=old_instance.id
    )
    try:
        deleted: list[str] = []
        created: list[str] = []
        monkeypatch.setattr(
            compose_manager, "delete_project", _make_fake_delete_project(db, deleted)
        )
        monkeypatch.setattr(app_service, "deploy", _make_fake_deploy(db, created))

        with pytest.raises(APIException) as exc_info:
            await orchestration_service.redeploy_instance(
                db,
                group_id=failed_group.id,
                instance_name="test-stack",
                selected_apps=["moviepilot"],
                app_configs={},
                shared_config={},
            )
        assert exc_info.value.status_code == 409
        assert "正在部署中" in str(exc_info.value)

        # 未清理、未重建
        assert deleted == []
        assert created == []
    finally:
        deploy_task_manager.fail_task(task_id, "测试清理")
