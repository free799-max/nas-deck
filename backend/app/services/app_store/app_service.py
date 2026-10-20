"""应用商店业务服务。"""

import asyncio
import logging
import re
from pathlib import Path

import yaml
from jinja2 import Environment, BaseLoader
from jsonschema import validate, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.background import create_background_task
from app.core.exceptions import APIException
from app.database import async_session
from app.models.app_store import App
from app.models.docker import DockerComposeProject
from app.models.orchestration import AppInstance
from app.schemas.app_store import AppCreate, AppUpdate
from app.services.app_store.app_validator import (
    extract_default_values,
    validate_app_definition,
)
from app.services.compose import compose_manager
from app.services.orchestration.deploy_task_service import deploy_task_manager
from app.services.system.port_allocator import (
    allocate_free_ports,
    get_used_ports,
    release_ports,
    reserve_ports,
)
from app.services.system import (
    StoragePathResolver,
    system_config_service,
)

logger = logging.getLogger(__name__)

# 允许上传的图标扩展名与大小限制
ALLOWED_ICON_EXTS = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
MAX_ICON_SIZE = 1024 * 1024  # 1MB

# 应用 name 合法字符（小写字母数字、中划线、下划线），用于防止路径穿越
APP_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _render_yaml_template(
    yaml_template: str,
    config_schema: dict,
    config: dict,
    project_name: str,
    app_name: str = "",
    resolver: StoragePathResolver | None = None,
) -> str:
    """使用 Jinja2 渲染 Compose YAML 模板。

    合并 Schema 默认值与用户配置后渲染，并校验结果为合法 YAML。
    同时注入宿主机/容器挂载基础路径变量及路径转换函数。
    """
    default_values = extract_default_values(config_schema or {})
    merged = {**default_values, **(config or {})}
    merged["project_name"] = project_name
    merged["app_name"] = app_name

    if resolver is not None:
        merged["host_mount_base"] = resolver.host_mount_base
        merged["container_mount_base"] = resolver.container_mount_base

    try:
        env = Environment(loader=BaseLoader(), autoescape=False)
        if resolver is not None:
            env.globals["make_host_path"] = resolver.make_host_path
            env.globals["make_container_path"] = resolver.make_container_path
            env.globals["to_host_path"] = resolver.to_host_path
            env.globals["to_container_path"] = resolver.to_container_path
        rendered = env.from_string(yaml_template).render(merged)
    except Exception as e:
        raise ValueError(f"应用模板渲染失败: {e}") from e

    try:
        yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        raise ValueError(f"渲染结果不是合法 YAML: {e}") from e

    return rendered


def _slugify(name: str) -> str:
    """将实例名称转换为合法 Compose 项目名。"""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9_-]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        raise ValueError("实例名称无法生成有效项目名")
    return name[:50]


def _extract_app_ports(config_schema: dict) -> list[str]:
    """从 JSON Schema 中提取类型为 integer 且命名包含 port 的字段名。"""
    ports = []
    for key, prop in (config_schema.get("properties") or {}).items():
        if "port" in key.lower() and prop.get("type") == "integer":
            ports.append(key)
    return ports


class AppService:
    """应用商店服务。

    负责应用查询与一键部署。
    """

    async def list_apps(
        self,
        db: AsyncSession,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[App]:
        """列出应用商店应用，支持分类和标签筛选。"""
        stmt = select(App)
        if category:
            stmt = stmt.where(App.category == category)
        stmt = stmt.order_by(App.category, App.display_name)
        result = await db.execute(stmt)
        apps = list(result.scalars().all())
        # tags 为 JSON 列，PostgreSQL 的 json 类型不支持 contains 查询，
        # 为保证 SQLite/PG 可移植性，标签过滤在 Python 侧做精确匹配
        if tag:
            apps = [a for a in apps if tag in (a.tags or [])]
        return apps

    async def get_app(self, db: AsyncSession, name: str) -> App:
        """获取单个应用详情。"""
        result = await db.execute(
            select(App).where(App.name == name)
        )
        app = result.scalar_one_or_none()
        if app is None:
            raise APIException("应用不存在", 404)
        return app

    async def _get_resolver(self, db: AsyncSession) -> StoragePathResolver:
        """读取系统存储配置构建路径解析器；未配置时使用根目录默认值。"""
        system_config = await system_config_service.get_or_create(db)
        resolver = StoragePathResolver(
            system_config.storage_host_root_dir,
            system_config.storage_docker_mount_dir,
        )
        if not resolver.configured:
            resolver = resolver.with_defaults()
        return resolver

    async def create_app(self, db: AsyncSession, data: AppCreate) -> App:
        """创建应用商店应用。

        校验 name 唯一性与格式、config_schema 与 yaml_template 合法性后落库。
        """
        if not APP_NAME_PATTERN.match(data.name):
            raise APIException(
                "应用标识 name 只能包含小写字母、数字、中划线和下划线，且以字母或数字开头",
                400,
            )

        existing = await db.execute(select(App).where(App.name == data.name))
        if existing.scalar_one_or_none():
            raise APIException(f"应用 '{data.name}' 已存在", 409)

        validate_app_definition(data.yaml_template, data.config_schema, data.image or "")

        app = App(**data.model_dump())
        db.add(app)
        await db.commit()
        await db.refresh(app)
        return app

    async def update_app(self, db: AsyncSession, name: str, data: AppUpdate) -> App:
        """更新应用商店应用（name 不可修改，内置应用允许编辑）。

        若更新了 yaml_template / config_schema / image，使用合并后的值重新校验。
        """
        app = await self.get_app(db, name)

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return app

        # 用合并后的值校验模板与 Schema 组合
        merged_template = update_data.get("yaml_template", app.yaml_template)
        merged_schema = update_data.get("config_schema", app.config_schema or {})
        merged_image = update_data.get("image", app.image) or ""
        if merged_template:
            validate_app_definition(merged_template, merged_schema, merged_image)

        for key, value in update_data.items():
            setattr(app, key, value)
        await db.commit()
        await db.refresh(app)
        return app

    async def delete_app(self, db: AsyncSession, name: str) -> None:
        """删除应用商店应用。

        内置应用禁止删除；存在部署实例的应用禁止删除。
        """
        app = await self.get_app(db, name)

        if app.is_builtin:
            raise APIException("内置应用禁止删除", 400)

        result = await db.execute(
            select(AppInstance).where(AppInstance.app_id == app.id)
        )
        if result.scalars().first() is not None:
            raise APIException("应用存在部署实例，请先删除相关实例", 409)

        await db.delete(app)
        await db.commit()

        # 清理已上传的图标文件（忽略失败）
        icon_dir = Path(settings.APP_ICON_DIR)
        for ext in ALLOWED_ICON_EXTS:
            icon_file = icon_dir / f"{name}{ext}"
            try:
                if icon_file.exists():
                    icon_file.unlink()
            except OSError:
                logger.warning("删除应用图标文件失败: %s", icon_file)

    async def preview_template(
        self,
        db: AsyncSession,
        yaml_template: str,
        config_schema: dict,
        image: str | None = None,
        app_name: str = "preview-app",
    ) -> dict:
        """预览未落库的应用模板渲染结果（创建/编辑页实时预览用）。

        校验失败时返回包含错误信息的字典，而不是抛异常。
        """
        resolver = await self._get_resolver(db)

        try:
            validate_app_definition(yaml_template, config_schema, image or "")
            rendered = _render_yaml_template(
                yaml_template,
                config_schema,
                {"image": image or "example/image"},
                "preview-project",
                app_name,
                resolver,
            )
        except (APIException, ValueError) as e:
            return {"yaml": None, "error": str(e)}

        return {"yaml": rendered, "error": None}

    async def save_app_icon(
        self, db: AsyncSession, name: str, filename: str, content: bytes
    ) -> App:
        """保存用户上传的应用图标，并更新 app.icon 为后端图标接口路径。"""
        app = await self.get_app(db, name)

        ext = Path(filename or "").suffix.lower()
        if ext not in ALLOWED_ICON_EXTS:
            raise APIException(
                f"不支持的图标格式 {ext or '(无扩展名)'}，仅支持: {', '.join(sorted(ALLOWED_ICON_EXTS))}",
                400,
            )
        if not content:
            raise APIException("图标文件为空", 400)
        if len(content) > MAX_ICON_SIZE:
            raise APIException("图标文件大小不能超过 1MB", 400)

        icon_dir = Path(settings.APP_ICON_DIR)
        icon_dir.mkdir(parents=True, exist_ok=True)

        # 删除旧的同名不同扩展名图标
        for old_ext in ALLOWED_ICON_EXTS:
            old_file = icon_dir / f"{name}{old_ext}"
            if old_ext != ext and old_file.exists():
                old_file.unlink()

        (icon_dir / f"{name}{ext}").write_bytes(content)

        app.icon = f"/api/apps/{name}/icon"
        await db.commit()
        await db.refresh(app)
        return app

    def get_app_icon_path(self, name: str) -> Path:
        """获取已上传应用图标的文件路径，不存在时抛出 404。"""
        if not APP_NAME_PATTERN.match(name):
            raise APIException("应用图标不存在", 404)
        icon_dir = Path(settings.APP_ICON_DIR)
        for ext in ALLOWED_ICON_EXTS:
            icon_file = icon_dir / f"{name}{ext}"
            if icon_file.exists():
                return icon_file
        raise APIException("应用图标不存在", 404)

    async def preview(
        self,
        db: AsyncSession,
        app_name: str,
        instance_name: str,
        config: dict,
    ) -> dict:
        """预览应用渲染后的 Compose YAML。

        复用部署前的 JSON Schema 校验与渲染逻辑，但不创建项目与实例，
        也不做端口冲突预检（端口检测留在部署阶段执行）。
        校验失败时返回包含错误信息的字典，而不是抛异常。
        """
        db_app = await self.get_app(db, app_name)

        # 0. 读取系统存储配置；未配置时使用根目录默认值继续预览，
        #    实际部署前仍需配置真实路径。
        resolver = await self._get_resolver(db)

        # 1. JSON Schema 校验与端口预检失败时，把错误返回给前端展示
        try:
            project_name, _ = await self._validate_and_prepare(
                db_app=db_app,
                instance_name=instance_name,
                config=config,
                check_ports=False,
            )
        except APIException as e:
            return {"yaml": None, "error": e.message}

        return {
            "yaml": self._render_app(
                db_app=db_app,
                config=config,
                project_name=project_name,
                resolver=resolver,
            ),
            "error": None,
        }

    async def _validate_and_prepare(
        self,
        db_app: App,
        instance_name: str,
        config: dict,
        check_ports: bool = True,
        port_start: int = 10000,
    ) -> tuple[str, list[int]]:
        """执行部署/预览前的公共校验，返回 (可用的项目名, 分配的端口列表)。

        Args:
            db_app: 应用模型
            instance_name: 实例名称
            config: 用户配置（部署时会原地改写其中的端口字段为自动分配的端口）
            check_ports: 是否进行端口分配；预览阶段为 False，部署阶段为 True
            port_start: 服务端口顺序分配的起始端口

        Note:
            返回的分配端口未预留，调用方需在部署前通过 reserve_ports 预留、
            部署结束后 release_ports 释放，防止并发部署重复分配。
        """
        allocated: list[int] = []

        # 1. JSON Schema 校验
        schema = db_app.config_schema or {}
        if schema:
            try:
                validate(instance=config, schema=schema)
            except ValidationError as e:
                raise APIException(f"配置校验失败: {e.message}", 400) from e

        # 2. 端口顺序分配（仅在部署时执行）：
        #    从起始端口开始按顺序分配，自动跳过已占用端口
        if check_ports:
            # 收集端口写入位置：(单端口字段名, None) 或 ("ports", 数组索引)
            targets: list[tuple[str, int | None]] = []

            # 2.1 单端口字段（按 schema properties 顺序，如 moviepilot_port: 3000）
            for key in _extract_app_ports(schema):
                if config.get(key) is not None:
                    targets.append((key, None))

            # 2.2 端口数组（按数组顺序，如 ports: [{local_port: 3000, ...}]）
            ports = config.get("ports")
            if isinstance(ports, list):
                for index, port_entry in enumerate(ports):
                    if not isinstance(port_entry, dict):
                        continue
                    if port_entry.get("local_port") is not None:
                        targets.append(("ports", index))

            if targets:
                used_ports = await asyncio.to_thread(get_used_ports)
                try:
                    allocated = allocate_free_ports(
                        used_ports, len(targets), port_start
                    )
                except ValueError as e:
                    raise APIException(str(e), 400) from e
                for (key, index), port in zip(targets, allocated):
                    if index is None:
                        config[key] = port
                    else:
                        config["ports"][index]["local_port"] = port

        # 3. 生成项目名
        return _slugify(instance_name), allocated

    async def deploy(
        self,
        db: AsyncSession,
        app_name: str,
        instance_name: str,
        config: dict,
        user_id: int | None = None,
    ) -> tuple[AppInstance, str]:
        """一键部署应用：校验并创建 deploying 实例，后台异步执行部署。

        返回 (AppInstance, task_id)，调用方应立即将 task_id 返回给前端。
        """
        db_app = await self.get_app(db, app_name)

        # 0. 读取并校验系统存储配置
        system_config = await system_config_service.get_or_create(db)
        resolver = StoragePathResolver(
            system_config.storage_host_root_dir,
            system_config.storage_docker_mount_dir,
        )
        resolver.validate()

        project_name, allocated_ports = await self._validate_and_prepare(
            db_app=db_app,
            instance_name=instance_name,
            config=config,
            port_start=system_config.service_port_start or 10000,
        )

        # 4. 检查项目名是否已存在
        existing_project = await db.execute(
            select(DockerComposeProject).where(
                DockerComposeProject.project_name == project_name
            )
        )
        if existing_project.scalar_one_or_none():
            raise APIException(
                f"项目名 {project_name} 已存在，请更换实例名称", 409
            )

        # 4.1 预留分配端口，防止并发部署（同组多应用同时部署）重复分配；
        #     部署结束由 _do_deploy 释放，此处异常需主动释放
        reserve_ports(allocated_ports)

        # 5-7. 渲染 YAML、创建实例与部署任务；任一失败都要释放预留端口
        try:
            # 5. 渲染 YAML
            rendered_yaml = self._render_app(
                db_app=db_app,
                config=config,
                project_name=project_name,
                resolver=resolver,
            )

            # 6. 创建 deploying 状态实例
            instance = AppInstance(
                app_id=db_app.id,
                instance_name=instance_name,
                config=config,
                orchestration_version=db_app.version,
                status="deploying",
            )
            db.add(instance)
            await db.flush()
            await db.refresh(instance)

            # 7. 创建部署任务并在主事件循环中启动后台协程。
            # 先建任务再提交实例：任务创建失败（如并发超限）时回滚，不留孤儿实例
            try:
                task_id = deploy_task_manager.create_task(
                    "app_deploy",
                    instance_id=instance.id,
                    meta={
                        "app_id": db_app.id,
                        "app_name": db_app.name,
                        "icon": db_app.icon,
                        "instance_name": instance_name,
                        "project_name": project_name,
                        "rendered_yaml": rendered_yaml,
                        "allocated_ports": allocated_ports,
                        "user_id": user_id,
                        "description": f"由应用 {db_app.display_name} 部署",
                    },
                )
            except RuntimeError as e:
                await db.rollback()
                raise APIException(str(e), 409) from e
            await db.commit()
        except Exception:
            release_ports(allocated_ports)
            raise

        create_background_task(self._do_deploy(task_id, instance.id))

        return instance, task_id

    async def _do_deploy(self, task_id: str, instance_id: int):
        """实际执行应用部署并更新实例状态。"""
        task = deploy_task_manager.get_task(task_id)
        if not task:
            logger.error("部署任务不存在: %s", task_id)
            return

        meta = task.get("meta") or {}
        rendered_yaml = meta.get("rendered_yaml", "")
        project_name = meta.get("project_name", "")
        user_id = meta.get("user_id")
        description = meta.get("description")

        def _progress(stage: str, percentage: int, message: str, detail: str | None = None):
            deploy_task_manager.update_progress(task_id, stage, percentage, message, detail)

        async with async_session() as db:
            try:
                _progress("preparing", 5, "准备部署")
                project = await compose_manager.create_project_async(
                    db,
                    project_name=project_name,
                    content=rendered_yaml,
                    user_id=user_id,
                    description=description,
                    progress_callback=_progress,
                    # 端口已在 deploy 阶段分配并预留，这里不再二次分配
                    allocate_ports=False,
                )

                # 更新实例为 running 并关联 project
                instance = await self.get_instance(db, instance_id)
                instance.project_id = project.id
                instance.status = "running"
                await db.commit()

                deploy_task_manager.complete_task(task_id)
            except Exception as e:
                logger.exception("应用部署失败: %s", e)
                error_msg = str(e)
                deploy_task_manager.fail_task(task_id, error_msg)

                try:
                    instance = await self.get_instance(db, instance_id)
                    instance.status = "error"
                    # 若项目已创建则关联 project_id，便于用户继续操作
                    if "project" in locals() and project:
                        instance.project_id = project.id
                    await db.commit()
                except Exception:
                    logger.exception("更新实例失败状态失败")
            finally:
                # 部署结束（成功/失败/超时），释放预留端口。
                # 成功时端口已绑定到容器，占用检测可接管；失败时端口未绑定，正确释放
                release_ports(meta.get("allocated_ports") or [])

    def _render_app(
        self,
        db_app: App,
        config: dict,
        project_name: str,
        resolver: StoragePathResolver,
    ) -> str:
        """渲染应用为 Compose YAML。"""
        if not db_app.yaml_template:
            raise APIException("应用模板为空，无法渲染", 500)

        # 把应用镜像名注入模板上下文，供 yaml_template 使用 {{ image }}
        merged_config = {**(config or {}), "image": db_app.image}

        try:
            return _render_yaml_template(
                db_app.yaml_template,
                db_app.config_schema,
                merged_config,
                project_name,
                db_app.name,
                resolver,
            )
        except ValueError as e:
            raise APIException(str(e), 500) from e

    async def get_instance(self, db: AsyncSession, instance_id: int) -> AppInstance:
        """获取单个应用实例（携带应用、项目及 Stack 关系）。"""
        from app.models.docker import DockerComposeProject

        result = await db.execute(
            select(AppInstance)
            .where(AppInstance.id == instance_id)
            .options(
                selectinload(AppInstance.app),
                selectinload(AppInstance.project).selectinload(
                    DockerComposeProject.stack
                ),
            )
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise APIException("应用实例不存在", 404)
        return instance
