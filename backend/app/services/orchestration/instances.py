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
    ) -> None:
        """删除编排实例组及其关联的应用实例与 Docker 项目。"""
        import logging

        from app.services.compose.compose_service import compose_manager

        logger = logging.getLogger(__name__)
        group = await self.get_instance_detail(db, instance_id)

        # 先清理有关联 Docker Compose 项目的实例；单个项目清理失败不应影响其余
        for instance in list(group.instances):
            if instance.project_id:
                project = await db.get(DockerComposeProject, instance.project_id)
                if project:
                    try:
                        await compose_manager.delete_project(db, project)
                    except Exception as e:
                        logger.warning(
                            "清理实例组 %s 的项目 %s 失败: %s",
                            instance_id,
                            project.project_name,
                            e,
                        )

        # 清理无项目实例（如导入的外部容器）及实例组本身
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
