"""应用商店业务服务。"""

import asyncio
import logging
import re
from pathlib import Path

import docker
import yaml
from jinja2 import Environment, BaseLoader
from jsonschema import validate, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
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
from app.services.system_config_service import (
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


def _parse_proc_net_tcp(path: str) -> set[int]:
    """读取 /proc/net/tcp 或 /proc/net/tcp6，提取处于 LISTEN 状态的本地端口。

    当 NasDeck 以 host network 模式运行时，读取到的是宿主机的监听端口；
    普通容器模式下读取的是容器自身命名空间内的端口，作为兜底信息使用。
    """
    listening: set[int] = set()
    try:
        with open(path, "r") as f:
            # 跳过第一行表头
            next(f, None)
            for line in f:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                # st 列：0A 表示 LISTEN
                if parts[3] != "0A":
                    continue
                local_addr = parts[1]
                if ":" not in local_addr:
                    continue
                _, port_hex = local_addr.rsplit(":", 1)
                try:
                    listening.add(int(port_hex, 16))
                except ValueError:
                    continue
    except (OSError, StopIteration):
        pass
    return listening


def _get_used_ports() -> set[int]:
    """获取宿主机上已被占用的端口。

    合并两个来源：
    1. Docker 容器已映射的端口（需要能访问 Docker daemon）；
    2. /proc/net/tcp* 中处于 LISTEN 状态的端口（host network 模式下为宿主机端口）。
    """
    used: set[int] = set()

    # 1. Docker 容器端口映射
    try:
        client = docker.from_env()
        for container in client.containers.list(all=True):
            host_config = container.attrs.get("HostConfig") or {}
            bindings = host_config.get("PortBindings") or {}
            for binding_list in bindings.values():
                if not isinstance(binding_list, list):
                    continue
                for binding in binding_list:
                    host_port = binding.get("HostPort")
                    if host_port:
                        try:
                            used.add(int(host_port))
                        except ValueError:
                            pass
    except Exception:
        # Docker 不可用时跳过
        pass

    # 2. 从 /proc/net/tcp* 读取监听端口
    used.update(_parse_proc_net_tcp("/proc/net/tcp"))
    used.update(_parse_proc_net_tcp("/proc/net/tcp6"))

    return used


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
        if tag:
            stmt = stmt.where(App.tags.contains(tag))
        stmt = stmt.order_by(App.category, App.display_name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

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
            project_name = await self._validate_and_prepare(
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
    ) -> str:
        """执行部署/预览前的公共校验，返回可用的项目名。

        Args:
            db_app: 应用模型
            instance_name: 实例名称
            config: 用户配置
            check_ports: 是否检查端口冲突；预览阶段为 False，部署阶段为 True
        """
        # 1. JSON Schema 校验
        schema = db_app.config_schema or {}
        if schema:
            try:
                validate(instance=config, schema=schema)
            except ValidationError as e:
                raise APIException(f"配置校验失败: {e.message}", 400) from e

        # 2. 端口冲突预检（仅在部署时执行）
        if check_ports:
            used_ports = _get_used_ports()

            # 2.1 单端口字段（如 moviepilot_port: 3000）
            port_keys = _extract_app_ports(schema)
            for key in port_keys:
                value = config.get(key)
                if value is not None and int(value) in used_ports:
                    raise APIException(
                        f"端口 {value} 已被占用，请修改 {key}", 409
                    )

            # 2.2 端口数组（如 ports: [{local_port: 3000, ...}]
            ports = config.get("ports")
            if isinstance(ports, list):
                for index, port_entry in enumerate(ports):
                    if not isinstance(port_entry, dict):
                        continue
                    local_port = port_entry.get("local_port")
                    if local_port is not None and int(local_port) in used_ports:
                        raise APIException(
                            f"端口 {local_port} 已被占用，请修改 ports[{index}].local_port", 409
                        )

        # 3. 生成项目名
        return _slugify(instance_name)

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

        project_name = await self._validate_and_prepare(
            db_app=db_app,
            instance_name=instance_name,
            config=config,
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
        await db.commit()

        # 7. 创建部署任务并在主事件循环中启动后台协程
        task_id = deploy_task_manager.create_task(
            "app_deploy",
            instance_id=instance.id,
            meta={
                "app_id": db_app.id,
                "app_name": db_app.name,
                "instance_name": instance_name,
                "project_name": project_name,
                "rendered_yaml": rendered_yaml,
                "user_id": user_id,
                "description": f"由应用 {db_app.display_name} 部署",
            },
        )

        asyncio.create_task(self._do_deploy(task_id, instance.id))

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
