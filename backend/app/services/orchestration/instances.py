"""应用编排实例查询与管理能力。"""

import asyncio
import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import APIException
from app.models.docker import DockerComposeProject
from app.models.orchestration import (
    AppInstance,
    AppOrchestration,
    AppOrchestrationInstance,
)

logger = logging.getLogger(__name__)


class InstanceMixin:
    """编排实例组的查询、更新与删除能力。"""

    async def list_instances(
        self,
        db: AsyncSession,
        category: str | None = None,
    ) -> list[AppOrchestrationInstance]:
        """列出编排实例组（一次部署/导入记录）。

        返回结果前会根据 Docker 实时刷新每个应用实例的状态。
        可选按分类筛选，返回结果按创建时间倒序排列。
        """
        stmt = (
            select(AppOrchestrationInstance)
            .join(AppOrchestration)
            .options(
                selectinload(AppOrchestrationInstance.orchestration),
                selectinload(AppOrchestrationInstance.instances).selectinload(
                    AppInstance.app
                ),
            )
        )
        if category:
            stmt = stmt.where(AppOrchestration.category == category)
        stmt = stmt.order_by(AppOrchestrationInstance.created_at.desc())
        result = await db.execute(stmt)
        groups = list(result.scalars().all())

        for group in groups:
            for instance in group.instances:
                await asyncio.to_thread(self._refresh_instance_status, instance)

        return groups

    async def get_instance(self, db: AsyncSession, instance_id: int) -> AppInstance:
        """获取单个编排实例（携带编排、项目及 Stack 关系）。"""
        result = await db.execute(
            select(AppInstance)
            .where(AppInstance.id == instance_id)
            .options(
                selectinload(AppInstance.orchestration),
                selectinload(AppInstance.project).selectinload(
                    DockerComposeProject.stack
                ),
            )
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise APIException("编排实例不存在", 404)
        return instance

    async def get_group(
        self,
        db: AsyncSession,
        group_id: int,
    ) -> AppOrchestrationInstance:
        """获取组合部署记录及其关联实例。"""
        result = await db.execute(
            select(AppOrchestrationInstance)
            .where(AppOrchestrationInstance.id == group_id)
            .options(
                selectinload(AppOrchestrationInstance.orchestration),
                selectinload(AppOrchestrationInstance.instances),
            )
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise APIException("组合部署记录不存在", 404)
        return group

    async def get_instance_detail(
        self,
        db: AsyncSession,
        instance_id: int,
    ) -> AppOrchestrationInstance:
        """获取编排实例组详情（含应用实例及应用信息）。

        返回前会根据 Docker 实时刷新每个应用实例的状态。
        """
        result = await db.execute(
            select(AppOrchestrationInstance)
            .where(AppOrchestrationInstance.id == instance_id)
            .options(
                selectinload(AppOrchestrationInstance.orchestration),
                selectinload(AppOrchestrationInstance.instances).selectinload(
                    AppInstance.app
                ),
            )
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise APIException("编排实例组不存在", 404)

        for instance in group.instances:
            await asyncio.to_thread(self._refresh_instance_status, instance)

        return group

    async def update_instance(
        self,
        db: AsyncSession,
        instance_id: int,
        instance_name: str | None = None,
        shared_config: dict | None = None,
        app_configs: dict | None = None,
    ) -> AppOrchestrationInstance:
        """更新编排实例组信息。"""
        group = await self.get_instance_detail(db, instance_id)
        if instance_name is not None:
            group.instance_name = instance_name
        if shared_config is not None:
            group.shared_config = shared_config
        if app_configs is not None:
            group.app_configs = app_configs
        await db.commit()
        await db.refresh(group)
        return group

    async def delete_instance(
        self,
        db: AsyncSession,
        instance_id: int,
        progress=None,
    ):
        """删除编排实例组及其关联的应用实例与 Docker 项目。

        删除前先把各应用自身的数据目录移入备份目录，避免同名重建时
        复用旧数据（如已初始化的数据库密码与本次部署不一致）。

        Args:
            progress: 可选进度回调 ``(stage, percentage, message, detail)``，
                供后台删除任务推送进度

        Returns:
            备份目录路径；未产生备份时返回 None
        """
        from app.services.app_store.app_service import _slugify
        from app.services.compose.compose_service import compose_manager
        from app.services.orchestration.backup import AppDataEntry, backup_app_data_dirs

        def report(
            stage: str, percentage: int, message: str, detail: str | None = None
        ) -> None:
            if progress is not None:
                progress(stage, percentage, message, detail)

        report("preparing", 5, "准备删除实例组")
        group = await self.get_instance_detail(db, instance_id)
        group_name = group.instance_name
        orchestration_name = group.orchestration.name if group.orchestration else None

        # 先记录应用信息：delete_project 会级联删除实例行
        projects: list[DockerComposeProject] = []
        entries: list[AppDataEntry] = []
        for instance in list(group.instances):
            app_name = instance.app.name if instance.app else None
            project = None
            if instance.project_id:
                project = await db.get(DockerComposeProject, instance.project_id)
            if project is not None:
                projects.append(project)
                project_name = project.project_name
            else:
                # 无关联项目的实例（部署中途失败、导入的外部容器）按项目名规则兜底
                try:
                    project_name = _slugify(instance.instance_name)
                except ValueError:
                    continue
            entries.append(
                AppDataEntry(
                    instance_name=instance.instance_name,
                    app_name=app_name,
                    project_name=project_name,
                    config=dict(instance.config or {}),
                )
            )

        # 先停止并移除容器；单个项目清理失败不应影响其余
        total = max(len(projects), 1)
        for index, project in enumerate(projects):
            report(
                "stopping_services",
                10 + int(50 * index / total),
                f"停止并移除容器（{index + 1}/{total}）",
                project.project_name,
            )
            try:
                await compose_manager.delete_project(db, project)
            except Exception as e:
                logger.warning(
                    "清理实例组 %s 的项目 %s 失败: %s",
                    instance_id,
                    project.project_name,
                    e,
                )

        # 容器已停止，再把应用数据目录移入备份目录
        report("backing_up_data", 65, "备份应用数据目录")
        backup_dir = await backup_app_data_dirs(
            db,
            entries,
            group_name=group_name,
            orchestration_name=orchestration_name,
            shared_config=group.shared_config,
            app_configs=group.app_configs,
        )

        # 清理无项目实例（如导入的外部容器）及实例组本身
        report("cleaning_records", 85, "清理实例组记录")
        await db.execute(
            delete(AppInstance).where(
                AppInstance.orchestration_group_id == instance_id
            )
        )
        await db.execute(
            delete(AppOrchestrationInstance).where(
                AppOrchestrationInstance.id == instance_id
            )
        )
        await db.commit()
        return backup_dir

    async def start_delete_instance(
        self,
        db: AsyncSession,
        instance_id: int,
    ) -> str:
        """创建后台删除任务并返回任务 ID。

        删除涉及停止容器与移动数据目录，耗时较长，改由部署任务通道
        推送进度，前端复用统一的进度弹窗展示。
        """
        from app.core.background import create_background_task
        from app.services.orchestration.deploy_task_service import deploy_task_manager

        group = await self.get_group(db, instance_id)

        deploying = [
            inst.instance_name
            for inst in group.instances
            if deploy_task_manager.has_active_task(instance_id=inst.id)
        ]
        if deploying or deploy_task_manager.has_active_group_task(instance_id):
            names = "、".join(deploying) or group.instance_name
            raise APIException(
                f"{names} 正在部署中，请等待完成后再删除", 409
            )

        task_id = deploy_task_manager.create_task(
            "orchestration_delete",
            # 不用 instance_id：它与 AppInstance.id 是不同命名空间，复用会误判
            meta={
                "instance_name": group.instance_name,
                "group_id": instance_id,
                "description": "删除实例组",
                "operation": "delete",
            },
        )
        create_background_task(self._do_delete(task_id, instance_id))
        return task_id

    async def _do_delete(self, task_id: str, instance_id: int) -> None:
        """执行后台删除任务并推送进度。"""
        from app.database import async_session
        from app.services.orchestration.deploy_task_service import deploy_task_manager

        def progress(
            stage: str, percentage: int, message: str, detail: str | None = None
        ) -> None:
            deploy_task_manager.update_progress(
                task_id, stage, percentage, message, detail
            )

        async with async_session() as db:
            try:
                backup_dir = await self.delete_instance(
                    db, instance_id, progress=progress
                )
            except Exception as exc:
                logger.exception("删除实例组 %s 失败", instance_id)
                await db.rollback()
                deploy_task_manager.fail_task(task_id, str(exc))
                return

        message = (
            "删除完成，应用数据已备份" if backup_dir else "删除完成"
        )
        deploy_task_manager.complete_task(task_id, message=message)
