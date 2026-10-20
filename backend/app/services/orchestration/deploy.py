"""应用编排组合部署能力。"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
from app.models.app_store import App
from app.models.docker import DockerComposeProject
from app.models.orchestration import (
    AppInstance,
    AppOrchestrationInstance,
)
from app.services.app_store import app_service
from app.services.orchestration.credentials import (
    inherit_stored_secrets,
    prepare_app_credentials,
)
from app.services.orchestration.deploy_task_service import deploy_task_manager
from app.services.orchestration.shared_config import merge_shared_config

logger = logging.getLogger(__name__)


class DeployMixin:
    """组合部署与重新部署能力。"""

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
        deployed_instances: dict[str, AppInstance] = {}
        pending_credentials: dict[str, dict] = {}

        try:
            for app_name in selected_apps:
                app_config = app_configs.get(app_name) or {}
                # 注入共享配置：volumes/env 数组追加合并，标量字段应用配置优先
                merged_config = merge_shared_config(
                    shared_config=shared_config,
                    app_config=app_config,
                    shared_schema=db_orchestration.shared_config_schema,
                    app_schema=app_map[app_name].config_schema,
                    app_name=app_name,
                )
                # 注入统一账号密码（env 类应用写入 env 数组）
                creds = await prepare_app_credentials(db, app_name, merged_config)
                if creds:
                    pending_credentials[app_name] = creds
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
                deployed_instances[app_name] = instance

            # 端口此时已分配完成，按实际端口写入各应用访问地址
            self._fill_access_urls(group, app_map, deployed_instances)
            group.status = "running"
            await db.commit()
        except Exception:
            group.status = "error"
            await db.commit()
            raise

        # 部署任务完成后把统一账号配置进真实服务（后台执行，不阻塞响应）
        self._schedule_provisioning(
            group.id, instance_name, selected_apps, task_ids, pending_credentials
        )

        return group, task_ids

    async def redeploy_instance(
        self,
        db: AsyncSession,
        group_id: int,
        instance_name: str,
        selected_apps: list[str],
        app_configs: dict[str, dict],
        shared_config: dict,
        user_id: int | None = None,
    ) -> tuple[AppOrchestrationInstance, list[str]]:
        """重新部署已有编排实例组。

        先清理 selected_apps 对应的旧应用实例及其 Compose 项目，
        再按与 deploy 相同的路径在原组上重新创建实例与后台部署任务。
        """
        from app.services.app_store.app_service import _slugify
        from app.services.compose.compose_service import compose_manager

        group = await self.get_group(db, group_id)
        db_orchestration = group.orchestration
        composition = db_orchestration.app_composition or []

        # 有正在进行的部署任务时拒绝修复：清理阶段会删除实例行，
        # 否则会打死后台任务并留下残留项目和卡住的任务槽位
        deploying = [
            inst.instance_name
            for inst in group.instances
            if deploy_task_manager.has_active_task(instance_id=inst.id)
        ]
        if deploying:
            raise APIException(
                f"以下应用正在部署中，请等待完成后再修复: {', '.join(deploying)}",
                409,
            )

        self._validate_composition(
            composition=composition,
            selected_apps=selected_apps,
        )

        app_map = await self._load_apps(db, selected_apps)
        missing = [name for name in selected_apps if name not in app_map]
        if missing:
            raise APIException(f"应用不存在: {', '.join(missing)}", 400)

        # 清理阶段：删除旧实例及其 Compose 项目；任一失败则整体报错，不半删
        # 删除前快照各应用的部署配置，修复时继承其中的密钥类 env
        stored_configs: dict[str, dict] = {}
        try:
            for app_name in selected_apps:
                app_id = app_map[app_name].id
                old_instances = [
                    inst for inst in group.instances if inst.app_id == app_id
                ]
                for old in old_instances:
                    if old.config and app_name not in stored_configs:
                        stored_configs[app_name] = dict(old.config)
                    cascade_deleted = False
                    if old.project_id:
                        project = await db.get(DockerComposeProject, old.project_id)
                        if project is not None:
                            # delete_project 会级联删除 project_id 关联的实例行并提交
                            await compose_manager.delete_project(db, project)
                            cascade_deleted = True
                    if not cascade_deleted:
                        # 兜底：实例未关联项目或关联项目已丢失时（如部署中途失败、
                        # 重启丢失协程），按项目名规则查找残留项目一并清理，避免同名 409
                        result = await db.execute(
                            select(DockerComposeProject).where(
                                DockerComposeProject.project_name
                                == _slugify(old.instance_name)
                            )
                        )
                        project = result.scalar_one_or_none()
                        if project is not None:
                            await compose_manager.delete_project(db, project)
                        await db.delete(old)
            await db.commit()
        except APIException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("重新部署：清理实例组 %s 的旧部署失败", group_id)
            raise APIException(f"清理旧部署失败: {e}", 500) from e

        # 全局互斥检测（旧实例已清理，不会误判自身）
        await self._check_global_conflicts(db, composition, selected_apps)

        # 在原组上按与 deploy 相同的路径重建实例与部署任务
        group.instance_name = instance_name
        group.shared_config = shared_config or {}
        group.status = "deploying"
        await db.commit()

        task_ids: list[str] = []
        deployed_instances: dict[str, AppInstance] = {}
        pending_credentials: dict[str, dict] = {}

        try:
            for app_name in selected_apps:
                app_config = app_configs.get(app_name) or {}
                # 注入共享配置：volumes/env 数组追加合并，标量字段应用配置优先
                merged_config = merge_shared_config(
                    shared_config=shared_config,
                    app_config=app_config,
                    shared_schema=db_orchestration.shared_config_schema,
                    app_schema=app_map[app_name].config_schema,
                    app_name=app_name,
                )
                # 修复时数据卷保留，继承上次部署的密钥类 env
                # （PostgreSQL/Redis 密码等仅首次初始化生效，重新随机必然不匹配）
                inherit_stored_secrets(stored_configs.get(app_name), merged_config)
                # 注入统一账号密码（env 类应用写入 env 数组）；
                # provision 类应用复用上次已配置的密码作为兜底/旧密码
                stored_entry = (group.app_configs or {}).get(app_name) or {}
                creds = await prepare_app_credentials(
                    db,
                    app_name,
                    merged_config,
                    fallback_password=stored_entry.get("password"),
                )
                if creds:
                    pending_credentials[app_name] = creds
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
                deployed_instances[app_name] = instance

            # 端口可能已重新分配，按最新配置刷新各应用访问地址，
            # 认证信息等既有 app_configs 条目保留
            self._fill_access_urls(group, app_map, deployed_instances)
            group.status = "running"
            await db.commit()
        except Exception:
            group.status = "error"
            await db.commit()
            raise

        # 部署任务完成后把统一账号配置进真实服务（后台执行，不阻塞响应）
        self._schedule_provisioning(
            group.id, instance_name, selected_apps, task_ids, pending_credentials
        )

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
