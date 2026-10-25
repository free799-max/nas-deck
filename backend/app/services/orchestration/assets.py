"""编排实例的离线资源管理（拷贝到容器）。"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background import create_background_task
from app.core.exceptions import APIException
from app.database import async_session
from app.models.app_store import App
from app.models.docker import DockerComposeProject
from app.models.orchestration import AppInstance
from app.services.apps.asset_copy import (
    AssetCopyError,
    copy_assets,
    find_container,
    is_running,
    marker_matches,
    read_marker,
)
from app.services.apps.offline_assets import OfflineAssetsProfile, get_profile
from app.services.orchestration.deploy_task_service import deploy_task_manager

logger = logging.getLogger(__name__)


class AssetsMixin:
    """组内应用的离线资源（插件依赖、浏览器内核）拷贝能力。"""

    async def get_app_assets(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
    ) -> dict:
        """查询应用的离线资源状态。"""
        profile = get_profile(app_name)
        if profile is None:
            return {"supported": False}

        container = await self._resolve_assets_container(db, group_id, app_name)
        status = {
            "supported": True,
            "app_name": app_name,
            "assets_image": profile.assets_image,
            "revision": profile.revision,
            "container": container,
            "running": False,
            "copied": False,
            "copied_at": None,
            "marker_image": None,
            "copies": [
                {
                    "label": copy.label,
                    "size": copy.size,
                    "source": copy.source,
                    "target": copy.target,
                }
                for copy in profile.copies
            ],
        }
        if not container:
            status["message"] = "应用容器不存在，请先部署或启动应用"
            return status

        status["running"] = await is_running(container)
        marker = await read_marker(container, profile.marker)
        status["copied"] = marker_matches(marker, profile)
        if marker:
            status["copied_at"] = marker.get("copied_at")
            status["marker_image"] = marker.get("image")
        return status

    async def copy_app_assets(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
    ) -> str:
        """把离线资源拷贝到应用容器（后台任务），返回任务 ID。"""
        profile = get_profile(app_name)
        if profile is None:
            raise APIException("该应用不支持离线数据拷贝", 400)
        container = await self._resolve_assets_container(db, group_id, app_name)
        if not container:
            raise APIException("应用容器不存在，请先部署或启动应用", 400)

        group = await self.get_group(db, group_id)
        task_id = deploy_task_manager.create_task(
            "app_assets_copy",
            meta={
                "instance_name": group.instance_name,
                "app_name": app_name,
                "description": "拷贝离线数据到容器",
                "operation": "assets_copy",
            },
            enforce_limit=False,
        )
        create_background_task(
            self._do_copy_app_assets(group_id, app_name, task_id)
        )
        return task_id

    async def _do_copy_app_assets(
        self,
        group_id: int,
        app_name: str,
        task_id: str,
    ) -> None:
        """后台执行拷贝并推送进度。"""

        def progress(
            stage: str,
            percentage: int,
            message: str,
            detail: str | None = None,
        ):
            deploy_task_manager.update_progress(
                task_id,
                stage,
                max(0, min(100, percentage)),
                message,
                detail,
            )

        try:
            async with async_session() as db:
                profile = get_profile(app_name)
                if profile is None:
                    raise AssetCopyError("该应用不支持离线数据拷贝")
                container = await self._resolve_assets_container(
                    db, group_id, app_name
                )
                if not container:
                    raise AssetCopyError("应用容器不存在，请先部署或启动应用")
                progress("copying_assets", 5, "准备拷贝离线数据")
                await copy_assets(container, profile, progress, force=True)
            deploy_task_manager.complete_task(task_id, "离线数据已拷贝到容器")
        except Exception as exc:  # noqa: BLE001 — 任务失败需要原样反馈给前端
            logger.exception("拷贝离线数据失败（%s/%s）", group_id, app_name)
            deploy_task_manager.fail_task(task_id, str(exc))

    async def _resolve_assets_container(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
    ) -> str | None:
        """解析组内应用对应的容器 ID。"""
        profile: OfflineAssetsProfile | None = get_profile(app_name)
        if profile is None:
            return None
        await self.get_group(db, group_id)
        result = await db.execute(
            select(AppInstance)
            .join(App, App.id == AppInstance.app_id)
            .where(
                AppInstance.orchestration_group_id == group_id,
                App.name == app_name,
            )
        )
        instance = result.scalars().first()
        if instance is None or not instance.project_id:
            return None
        project = await db.get(DockerComposeProject, instance.project_id)
        if project is None:
            return None
        return await find_container(project.project_name, profile.service)
