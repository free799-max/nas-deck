"""应用编排业务服务。"""

import re

import docker
import yaml
from jinja2 import Environment, BaseLoader
from jsonschema import validate, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import APIException
from app.models.docker import DockerComposeProject
from app.models.orchestration import AppInstance, AppOrchestration
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
    orchestration_name: str = "",
    resolver: StoragePathResolver | None = None,
) -> str:
    """使用 Jinja2 渲染 Compose YAML 模板。

    合并 Schema 默认值与用户配置后渲染，并校验结果为合法 YAML。
    同时注入宿主机/容器挂载基础路径变量及路径转换函数。
    """
    default_values = _extract_default_values(config_schema or {})
    merged = {**default_values, **(config or {})}
    merged["project_name"] = project_name
    merged["orchestration_name"] = orchestration_name

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
        raise ValueError(f"编排模板渲染失败: {e}") from e

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


def _extract_orchestration_ports(config_schema: dict) -> list[str]:
    """从 JSON Schema 中提取类型为 integer 且命名包含 port 的字段名。"""
    ports = []
    for key, prop in (config_schema.get("properties") or {}).items():
        if "port" in key.lower() and prop.get("type") == "integer":
            ports.append(key)
    return ports


def _get_used_ports() -> set[int]:
    """获取宿主机上已被容器占用的端口。"""
    used = set()
    try:
        client = docker.from_env()
        for container in client.containers.list(all=True):
            host_config = container.attrs.get("HostConfig") or {}
            bindings = (host_config.get("PortBindings") or {})
            for container_port, binding_list in bindings.items():
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
        # Docker 不可用时跳过端口预检
        pass
    return used


class OrchestrationService:
    """应用编排服务。

    负责编排查询与一键部署。
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
        config: dict,
        user_id: int | None = None,
    ) -> AppInstance:
        """一键部署编排实例。"""
        db_orchestration = await self.get_orchestration(db, orchestration_name)

        # 0. 读取并校验系统存储配置
        system_config = await system_config_service.get_or_create(db)
        resolver = StoragePathResolver(
            system_config.storage_host_root_dir,
            system_config.storage_docker_mount_dir,
        )
        resolver.validate()

        # 1. JSON Schema 校验
        schema = db_orchestration.config_schema or {}
        if schema:
            try:
                validate(instance=config, schema=schema)
            except ValidationError as e:
                raise APIException(f"配置校验失败: {e.message}", 400) from e

        # 2. 端口冲突预检
        used_ports = _get_used_ports()
        port_keys = _extract_orchestration_ports(schema)
        for key in port_keys:
            value = config.get(key)
            if value is not None and int(value) in used_ports:
                raise APIException(
                    f"端口 {value} 已被其他容器占用，请修改 {key}", 409
                )

        # 3. 生成项目名
        project_name = _slugify(instance_name)

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
        rendered_yaml = self._render_orchestration(
            db_orchestration=db_orchestration,
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
                description=f"由编排 {db_orchestration.display_name} 部署",
            )
        except Exception as e:
            raise APIException(f"部署失败: {e}", 500) from e

        # 7. 创建 AppInstance 记录
        instance = AppInstance(
            orchestration_id=db_orchestration.id,
            project_id=project.id,
            instance_name=instance_name,
            config=config,
            orchestration_version=db_orchestration.version,
            status="running",
        )
        db.add(instance)
        await db.flush()
        await db.refresh(instance)

        await db.commit()
        return await self.get_instance(db, instance.id)

    def _render_orchestration(
        self,
        db_orchestration: AppOrchestration,
        config: dict,
        project_name: str,
        resolver: StoragePathResolver,
    ) -> str:
        """渲染编排为 Compose YAML。"""
        if not db_orchestration.yaml_template:
            raise APIException("编排模板为空，无法渲染", 500)

        try:
            return _render_yaml_template(
                db_orchestration.yaml_template,
                db_orchestration.config_schema,
                config,
                project_name,
                db_orchestration.name,
                resolver,
            )
        except ValueError as e:
            raise APIException(str(e), 500) from e

    async def get_instance(self, db: AsyncSession, instance_id: int) -> AppInstance:
        """获取单个编排实例（携带编排与项目关系）。"""
        result = await db.execute(
            select(AppInstance)
            .where(AppInstance.id == instance_id)
            .options(
                selectinload(AppInstance.orchestration),
                selectinload(AppInstance.project),
            )
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise APIException("编排实例不存在", 404)
        return instance


# 全局单例
orchestration_service = OrchestrationService()
