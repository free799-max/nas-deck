"""应用编排业务服务。"""

import socket

import docker
from sqlalchemy import delete, select
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
from app.schemas.orchestration import (
    ContainerMatch,
    ImportCandidateApp,
)
from app.services.app_store import app_service
from app.services.apps import AuthVerifyResult, get_client


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

    async def verify_app_auth(
        self,
        app_name: str,
        config: dict,
    ) -> AuthVerifyResult:
        """调用应用专属客户端验证认证信息。"""
        client_cls = get_client(app_name)
        client = client_cls()
        return await client.verify_auth(config)

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

    async def scan_import_candidates(
        self,
        db: AsyncSession,
        orchestration_name: str,
    ) -> list[ImportCandidateApp]:
        """扫描运行中的 Docker 容器，返回可导入的应用候选列表。

        匹配规则：容器镜像（去除 tag）包含应用商店 App 的镜像名（去除 tag）时视为命中。
        只返回 running 状态的容器，减少无关噪声。
        """
        db_orchestration = await self.get_orchestration(db, orchestration_name)
        composition = db_orchestration.app_composition or []

        app_names = [item.get("app_name") for item in composition if item.get("app_name")]
        app_map = await self._load_apps(db, app_names)

        containers = self._list_running_containers()

        candidates_by_app: dict[str, list[ContainerMatch]] = {
            name: [] for name in app_names
        }
        for container in containers:
            container_id = container.id[:12]
            container_name = container.name
            image = str(container.image.tags[0]) if container.image.tags else "unknown"
            image_base = image.split(":")[0].lower()

            network_ip, container_port, host_port = self._extract_network_info(container)
            suggested_url = self._build_suggested_url(
                network_ip=network_ip,
                host_port=host_port,
                container_port=container_port,
            )

            for item in composition:
                app_name = item.get("app_name")
                app = app_map.get(app_name)
                if not app or not app.image:
                    continue
                app_image_base = app.image.split(":")[0].lower()
                if app_image_base and app_image_base in image_base:
                    candidates_by_app[app_name].append(
                        ContainerMatch(
                            container_id=container_id,
                            container_name=container_name,
                            image=image,
                            network_ip=network_ip,
                            host_port=host_port,
                            container_port=container_port,
                            suggested_url=suggested_url,
                        )
                    )

        result: list[ImportCandidateApp] = []
        for item in composition:
            app_name = item.get("app_name")
            app = app_map.get(app_name)
            candidates = candidates_by_app.get(app_name, [])
            result.append(
                ImportCandidateApp(
                    app_name=app_name,
                    display_name=app.display_name if app else app_name,
                    icon=app.icon if app else None,
                    relation=item.get("relation", "optional"),
                    group=item.get("group"),
                    matched=len(candidates) > 0,
                    candidates=candidates,
                )
            )
        return result

    async def import_orchestration(
        self,
        db: AsyncSession,
        orchestration_name: str,
        instance_name: str,
        selected_apps: list[str],
        app_configs: dict[str, dict],
        shared_config: dict,
        user_id: int | None = None,
    ) -> tuple[AppOrchestrationInstance, list[int]]:
        """导入已有 Docker 部署为编排实例。

        创建 AppOrchestrationInstance 记录，并为每个选中的应用创建 AppInstance，
        将容器运行时信息写入 AppInstance.config。返回组合部署记录及创建的应用实例 ID 列表。
        """
        db_orchestration = await self.get_orchestration(db, orchestration_name)
        composition = db_orchestration.app_composition or []

        self._validate_composition(
            composition=composition,
            selected_apps=selected_apps,
        )

        app_map = await self._load_apps(db, selected_apps)
        missing = [name for name in selected_apps if name not in app_map]
        if missing:
            raise APIException(f"应用不存在: {', '.join(missing)}", 400)

        # 重新扫描一次容器，获取选中应用对应的运行时信息
        candidates = await self.scan_import_candidates(db, orchestration_name)
        candidate_map = {item.app_name: item for item in candidates}

        group = AppOrchestrationInstance(
            orchestration_id=db_orchestration.id,
            instance_name=instance_name,
            shared_config=shared_config or {},
            app_configs=app_configs or {},
            status="running",
        )
        db.add(group)
        await db.flush()
        await db.refresh(group)

        created_instance_ids: list[int] = []
        for app_name in selected_apps:
            app = app_map[app_name]
            candidate = candidate_map.get(app_name)
            app_config = app_configs.get(app_name) or {}
            selected_container_id = app_config.get("selected_container_id")

            selected_container = None
            if candidate and candidate.candidates:
                if selected_container_id:
                    selected_container = next(
                        (c for c in candidate.candidates if c.container_id == selected_container_id),
                        None,
                    )
                if selected_container is None:
                    selected_container = candidate.candidates[0]

            runtime_config: dict = {
                "imported": True,
                "source": "docker_container",
            }
            if selected_container:
                runtime_config.update({
                    "container_id": selected_container.container_id,
                    "container_name": selected_container.container_name,
                    "container_image": selected_container.image,
                    "network_ip": selected_container.network_ip,
                    "host_port": selected_container.host_port,
                    "container_port": selected_container.container_port,
                    "suggested_url": selected_container.suggested_url,
                })

            # 将用户填写的认证信息也合并到实例配置，方便后续统一读取
            runtime_config.update(app_config)

            instance = AppInstance(
                app_id=app.id,
                orchestration_id=db_orchestration.id,
                orchestration_group_id=group.id,
                instance_name=f"{instance_name}-{app_name}",
                config=runtime_config,
                orchestration_version=db_orchestration.version,
                status="running",
            )
            db.add(instance)
            await db.flush()
            await db.refresh(instance)
            created_instance_ids.append(instance.id)

        await db.commit()
        return group, created_instance_ids

    def _list_running_containers(self) -> list:
        """列出当前运行中的 Docker 容器，Docker 不可用时返回空列表。"""
        try:
            client = docker.from_env()
            return client.containers.list(all=False)
        except docker.errors.DockerException:
            return []

    def _extract_network_info(
        self,
        container,
    ) -> tuple[str | None, str | None, int | None]:
        """从容器的 attrs 中提取网络 IP、容器端口和宿主机端口。"""
        attrs = container.attrs or {}
        network_settings = attrs.get("NetworkSettings", {}) or {}
        host_config = attrs.get("HostConfig", {}) or {}

        # 1. 网络 IP：优先取第一个非空 IPAddress
        network_ip = None
        networks = network_settings.get("Networks") or {}
        for net_info in networks.values():
            ip = net_info.get("IPAddress")
            if ip:
                network_ip = ip
                break

        # 2. 容器端口：从 Config.ExposedPorts 或 PortBindings 推断主端口
        container_port = None
        exposed_ports = (attrs.get("Config", {}) or {}).get("ExposedPorts") or {}
        if exposed_ports:
            # 取第一个 TCP 端口，如 "8096/tcp"
            for port_key in exposed_ports.keys():
                if "/tcp" in port_key:
                    container_port = port_key.replace("/tcp", "")
                    break

        # 3. 宿主机端口：从 PortBindings 找主端口
        host_port = None
        port_bindings = network_settings.get("Ports") or {}
        for port_key, bindings in port_bindings.items():
            if isinstance(bindings, list) and bindings:
                hp = bindings[0].get("HostPort")
                if hp:
                    try:
                        host_port = int(hp)
                    except ValueError:
                        pass
                    if "/tcp" in port_key:
                        container_port = port_key.replace("/tcp", "")
                    break

        # 兜底：host network 模式下从 /proc/net/tcp 读取监听端口
        if host_port is None and host_config.get("NetworkMode") == "host":
            host_port = self._guess_host_network_port(container)
            if host_port and container_port is None:
                container_port = str(host_port)

        return network_ip, container_port, host_port

    def _guess_host_network_port(self, container) -> int | None:
        """host network 模式下，尝试从容器内 /proc/net/tcp 读取 LISTEN 端口。"""
        try:
            result = container.exec_run("cat /proc/net/tcp")
            output = result.output.decode("utf-8", errors="replace")
            listening: set[int] = set()
            for line in output.splitlines()[1:]:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
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
            # 排除常见系统端口，取最小的一个作为候选
            for excluded in {22, 80, 443}:
                listening.discard(excluded)
            return min(listening) if listening else None
        except Exception:
            return None

    def _get_host_ip(self) -> str:
        """获取宿主机在内网中的本地 IP，失败时回退到 localhost。"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.5)
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "localhost"

    def _build_suggested_url(
        self,
        network_ip: str | None,
        host_port: int | None,
        container_port: str | None,
    ) -> str | None:
        """根据网络信息构造建议访问地址。

        当容器映射了宿主机端口时，优先使用宿主机内网 IP + 宿主机端口；
        否则回退到容器内网 IP + 容器端口。
        """
        if host_port:
            return f"http://{self._get_host_ip()}:{host_port}"
        if network_ip and container_port:
            return f"http://{network_ip}:{container_port}"
        return None

    def _refresh_instance_status(self, instance: AppInstance) -> None:
        """根据 Docker 容器实际运行状态刷新 AppInstance.status。

        优先读取 instance.config 中的 container_id；未找到时尝试用
        container_name 兜底。Docker 不可用时保持原状态不变。
        """
        config = instance.config or {}
        container_id = config.get("container_id")
        if not container_id:
            container_name = config.get("container_name")
            if not container_name:
                return
            container_id = container_name

        try:
            client = docker.from_env()
            container = client.containers.get(container_id)
            container.reload()
        except docker.errors.NotFound:
            instance.status = "stopped"
            return
        except docker.errors.DockerException:
            return

        state = container.attrs.get("State", {}) or {}
        status = state.get("Status", container.status)
        if status == "running":
            instance.status = "running"
        elif status in {"exited", "dead"}:
            instance.status = "stopped"
        elif status == "paused":
            instance.status = "stopped"
        else:
            instance.status = status

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
                self._refresh_instance_status(instance)

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
            self._refresh_instance_status(instance)

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


# 全局单例
orchestration_service = OrchestrationService()
