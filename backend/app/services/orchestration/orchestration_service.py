"""应用编排业务服务。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import APIException
from app.models.app_store import App
from app.models.docker import DockerComposeProject
from app.models.orchestration import (
    AppInstance,
    AppOrchestration,
    AppOrchestrationInstance,
)
from app.services.app_store import app_service


class OrchestrationService:
    """应用编排服务。

    负责自动化分类组合模板的查询与组合部署。
    一个编排对应一组应用商店 App 的组合关系，部署时拆分为多个独立的
    Docker Compose 项目。
    """

    async def list_orchestrations(
        self,
        db: AsyncSession,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[AppOrchestration]:
        """列出应用编排，支持分类和标签筛选。"""
        stmt = select(AppOrchestration)
        if category:
            stmt = stmt.where(AppOrchestration.category == category)
        if tag:
            stmt = stmt.where(AppOrchestration.tags.contains(tag))
        stmt = stmt.order_by(AppOrchestration.category, AppOrchestration.display_name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_orchestration(self, db: AsyncSession, name: str) -> AppOrchestration:
        """获取单个编排详情。"""
        result = await db.execute(
            select(AppOrchestration).where(AppOrchestration.name == name)
        )
        orchestration = result.scalar_one_or_none()
        if orchestration is None:
            raise APIException("编排不存在", 404)
        return orchestration

    async def deploy(
        self,
        db: AsyncSession,
        orchestration_name: str,
        instance_name: str,
        selected_apps: list[str],
        app_configs: dict[str, dict],
        shared_config: dict,
        user_id: int | None = None,
    ) -> tuple[AppOrchestrationInstance, list[str]]:
        """组合部署：按 AppOrchestration.app_composition 的定义，批量部署多个独立 App。

        返回组合部署记录和每个 App 对应的部署任务 ID 列表。
        """
        db_orchestration = await self.get_orchestration(db, orchestration_name)

        composition = db_orchestration.app_composition or []
        self._validate_composition(
            composition=composition,
            selected_apps=selected_apps,
        )

        # 校验所选 App 是否存在于应用商店
        app_map = await self._load_apps(db, selected_apps)
        missing = [name for name in selected_apps if name not in app_map]
        if missing:
            raise APIException(f"应用不存在: {', '.join(missing)}", 400)

        # 全局互斥检测
        await self._check_global_conflicts(db, composition, selected_apps)

        # 创建组合部署记录
        group = AppOrchestrationInstance(
            orchestration_id=db_orchestration.id,
            instance_name=instance_name,
            shared_config=shared_config or {},
            status="deploying",
        )
        db.add(group)
        await db.flush()
        await db.refresh(group)
        await db.commit()

        task_ids: list[str] = []

        try:
            for app_name in selected_apps:
                app_config = app_configs.get(app_name) or {}
                # 注入共享配置，让各 App 的 yaml_template 可以引用
                merged_config = {**(shared_config or {}), **app_config}
                sub_instance_name = f"{instance_name}-{app_name}"

                instance, task_id = await app_service.deploy(
                    db,
                    app_name=app_name,
                    instance_name=sub_instance_name,
                    config=merged_config,
                    user_id=user_id,
                )

                # 关联到组合部署组
                instance.orchestration_id = db_orchestration.id
                instance.orchestration_group_id = group.id
                await db.commit()

                task_ids.append(task_id)

            group.status = "running"
            await db.commit()
        except Exception:
            group.status = "error"
            await db.commit()
            raise

        return group, task_ids

    def _validate_composition(
        self,
        composition: list[dict],
        selected_apps: list[str],
    ) -> None:
        """校验用户选择的应用是否满足组合关系。"""
        selected_set = set(selected_apps)
        composition_by_name = {item.get("app_name"): item for item in composition}

        # 1. 必选应用必须选中
        for item in composition:
            if item.get("relation") == "required":
                app_name = item.get("app_name")
                if app_name not in selected_set:
                    raise APIException(
                        f"应用 {app_name} 为必选应用，必须部署", 400
                    )

        # 2. 所选应用必须在组合定义中
        for app_name in selected_apps:
            if app_name not in composition_by_name:
                raise APIException(
                    f"应用 {app_name} 不在当前编排组合中", 400
                )

        # 3. 组合内互斥检测
        for item in composition:
            app_name = item.get("app_name")
            if app_name not in selected_set:
                continue
            conflict_with = item.get("conflict_with") or []
            for conflict_app in conflict_with:
                if conflict_app in selected_set:
                    raise APIException(
                        f"应用 {app_name} 与 {conflict_app} 互斥，不能同时部署", 409
                    )

    async def _load_apps(
        self,
        db: AsyncSession,
        app_names: list[str],
    ) -> dict[str, App]:
        """批量加载应用商店应用。"""
        if not app_names:
            return {}
        result = await db.execute(
            select(App).where(App.name.in_(app_names))
        )
        apps = result.scalars().all()
        return {app.name: app for app in apps}

    async def _check_global_conflicts(
        self,
        db: AsyncSession,
        composition: list[dict],
        selected_apps: list[str],
    ) -> None:
        """检测已部署实例中是否存在与本次部署应用互斥的运行中实例。"""
        selected_set = set(selected_apps)
        conflict_map: dict[str, set[str]] = {}

        for item in composition:
            app_name = item.get("app_name")
            if app_name not in selected_set:
                continue
            for conflict_app in item.get("conflict_with") or []:
                conflict_map.setdefault(conflict_app, set()).add(app_name)

        if not conflict_map:
            return

        result = await db.execute(
            select(AppInstance, App.name)
            .join(App, AppInstance.app_id == App.id)
            .where(
                App.name.in_(conflict_map.keys()),
                AppInstance.status == "running",
            )
        )
        rows = result.all()
        if rows:
            conflict_app = rows[0][1]
            conflicting_selected = conflict_map[conflict_app]
            raise APIException(
                f"应用 {conflict_app} 已在运行，与 {', '.join(conflicting_selected)} 互斥",
                409,
            )

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


# 全局单例
orchestration_service = OrchestrationService()
