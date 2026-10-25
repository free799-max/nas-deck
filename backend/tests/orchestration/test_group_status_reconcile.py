"""实例组卡在 deploying 时的读取恢复测试。"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401 — 注册所有模型到 Base.metadata
from app.database import Base
from app.models.orchestration import AppOrchestration, AppOrchestrationInstance
from app.services.orchestration.deploy_task_service import deploy_task_manager
from app.services.orchestration.service import OrchestrationService


@pytest.fixture(name="session_factory")
async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    yield factory
    await engine.dispose()


async def _create_group(
    factory,
    *,
    status: str = "deploying",
    age_seconds: int = 300,
) -> int:
    async with factory() as db:
        template = AppOrchestration(
            name="comics", display_name="漫画自动化", category="comics"
        )
        db.add(template)
        await db.flush()
        group = AppOrchestrationInstance(
            orchestration_id=template.id,
            instance_name="comic-auto",
            status=status,
            created_at=datetime.now() - timedelta(seconds=age_seconds),
        )
        db.add(group)
        await db.commit()
        return group.id


async def _group_status(factory, group_id: int) -> str:
    async with factory() as db:
        group = (
            await db.execute(
                select(AppOrchestrationInstance).where(
                    AppOrchestrationInstance.id == group_id
                )
            )
        ).scalar_one()
        return group.status


@pytest.mark.asyncio
async def test_stale_deploying_group_is_marked_error(session_factory):
    """进程重启后残留的 deploying 组没有任何任务，读取时置为 error。"""
    group_id = await _create_group(session_factory)
    service = OrchestrationService()

    async with session_factory() as db:
        await service.list_instances(db)

    assert await _group_status(session_factory, group_id) == "error"


@pytest.mark.asyncio
async def test_deploying_group_with_active_upgrade_task_is_kept(session_factory):
    """确实有组级升级任务运行时不能误判为中断。"""
    group_id = await _create_group(session_factory)
    task_id = deploy_task_manager.create_task(
        "orchestration_upgrade",
        enforce_limit=False,
        meta={"orchestration_group_id": group_id},
    )
    service = OrchestrationService()

    async with session_factory() as db:
        await service.list_instances(db)

    assert await _group_status(session_factory, group_id) == "deploying"
    deploy_task_manager.complete_task(task_id)


@pytest.mark.asyncio
async def test_deploying_group_with_active_delete_task_is_kept(session_factory):
    """删除任务用 meta.group_id 标记，也要被识别为进行中的组任务。"""
    group_id = await _create_group(session_factory)
    task_id = deploy_task_manager.create_task(
        "orchestration_delete",
        enforce_limit=False,
        meta={"group_id": group_id},
    )
    service = OrchestrationService()

    async with session_factory() as db:
        await service.get_instance_detail(db, group_id)

    assert await _group_status(session_factory, group_id) == "deploying"
    deploy_task_manager.complete_task(task_id)


@pytest.mark.asyncio
async def test_fresh_deploying_group_is_not_touched(session_factory):
    """刚创建的组可能还没创建任务，宽限期内不置 error。"""
    group_id = await _create_group(session_factory, age_seconds=10)
    service = OrchestrationService()

    async with session_factory() as db:
        await service.list_instances(db)

    assert await _group_status(session_factory, group_id) == "deploying"
