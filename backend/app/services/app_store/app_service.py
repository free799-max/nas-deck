"""应用商店业务服务。"""

import re

import docker
import yaml
from jinja2 import Environment, BaseLoader
from jsonschema import validate, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import APIException
from app.models.app_store import App
from app.models.docker import DockerComposeProject
from app.models.orchestration import AppInstance
from app.services.compose import compose_manager
from app.services.system_config_service import (
    StoragePathResolver,
    system_config_service,
)


def _extract_default_values(config_schema: dict) -> dict:
    """从 JSON Schema 的 properties 中提取各字段的 default 值。"""
    defaults: dict = {}
    for key, prop in (config_schema.get("properties") or {}).items():
        if "default" in prop:
            defaults[key] = prop["default"]
    return defaults


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
    default_values = _extract_default_values(config_schema or {})
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
        system_config = await system_config_service.get_or_create(db)
        resolver = StoragePathResolver(
            system_config.storage_host_root_dir,
            system_config.storage_docker_mount_dir,
        )
        if not resolver.configured:
            resolver = resolver.with_defaults()

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
    ) -> AppInstance:
        """一键部署应用。"""
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

        # 6. 创建 Compose 项目并部署
        try:
            project = await compose_manager.create_project(
                db,
                project_name=project_name,
                content=rendered_yaml,
                user_id=user_id,
                description=f"由应用 {db_app.display_name} 部署",
            )
        except Exception as e:
            raise APIException(f"部署失败: {e}", 500) from e

        # 7. 创建 AppInstance 记录
        instance = AppInstance(
            app_id=db_app.id,
            project_id=project.id,
            instance_name=instance_name,
            config=config,
            orchestration_version=db_app.version,
            status="running",
        )
        db.add(instance)
        await db.flush()
        await db.refresh(instance)

        await db.commit()
        return await self.get_instance(db, instance.id)

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

        try:
            return _render_yaml_template(
                db_app.yaml_template,
                db_app.config_schema,
                config,
                project_name,
                db_app.name,
                resolver,
            )
        except ValueError as e:
            raise APIException(str(e), 500) from e

    async def get_instance(self, db: AsyncSession, instance_id: int) -> AppInstance:
        """获取单个应用实例（携带应用与项目关系）。"""
        result = await db.execute(
            select(AppInstance)
            .where(AppInstance.id == instance_id)
            .options(
                selectinload(AppInstance.app),
                selectinload(AppInstance.project),
            )
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise APIException("应用实例不存在", 404)
        return instance
