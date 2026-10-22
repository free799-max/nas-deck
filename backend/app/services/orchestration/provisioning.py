"""应用编排部署后账号自动配置（provisioning）能力。"""

import asyncio
import logging
from urllib.parse import urlparse

import docker

from app.core.background import create_background_task
from app.core.exceptions import APIException
from app.database import async_session
from app.models.orchestration import AppInstance
from app.services.apps import ProvisionResult, get_client
from app.services.docker import docker_manager
from app.services.orchestration.deploy_task_service import deploy_task_manager

logger = logging.getLogger(__name__)


class ProvisionMixin:
    """部署任务完成后把统一账号配置进真实服务的能力。"""

    def _schedule_provisioning(
        self,
        group_id: int,
        instance_name: str,
        selected_apps: list[str],
        task_ids: list[str],
        pending_credentials: dict[str, dict],
    ) -> str | None:
        """为部署后的账号自动配置启动后台协程。

        每个待配置应用等待其部署任务结束后，由应用客户端把统一
        账号密码配置进真实服务并复验，结果写入 group.app_configs。

        Returns:
            进度跟踪任务 ID；没有待配置应用时返回 None
        """
        # 延迟导入：避免 app_store -> orchestration -> provisioning 的循环依赖
        from app.services.app_store.app_service import _slugify

        items = []
        for app_name, task_id in zip(selected_apps, task_ids, strict=True):
            creds = pending_credentials.get(app_name)
            if not creds:
                continue
            items.append(
                {
                    "app_name": app_name,
                    "task_id": task_id,
                    "project_name": _slugify(f"{instance_name}-{app_name}"),
                    "credentials": creds,
                }
            )
        if not items:
            return None

        # 部署后的配置与装配耗时较长，单独建一个跟踪任务让前端继续
        # 展示进度，避免用户误以为部署完成后没有自动配置
        progress_task_id = deploy_task_manager.create_task(
            "orchestration_provision",
            meta={
                "instance_name": instance_name,
                "orchestration_group_id": group_id,
                "description": "自动配置账号与应用集成",
                "operation": "provision",
            },
            enforce_limit=False,
        )
        create_background_task(
            self._provision_group(group_id, items, progress_task_id)
        )
        return progress_task_id

    async def _wait_task_terminal(self, task_id: str, timeout: float = 1800.0) -> str:
        """轮询部署任务直到终态，返回 completed / failed。"""
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            task = deploy_task_manager.get_task(task_id)
            if task is None or task.get("status") != "deploying":
                return (task or {}).get("status") or "failed"
            await asyncio.sleep(2)
        return "failed"

    async def _provision_group(
        self,
        group_id: int,
        items: list[dict],
        progress_task_id: str | None = None,
    ) -> None:
        """逐个应用执行账号自动配置并落库，失败只记录不影响部署结果。

        同时把等待部署、配置账号、自动装配的阶段推送到进度任务，
        前端在部署进度弹窗中持续展示，直到配置与装配全部结束。
        """
        total = len(items)
        failed: list[str] = []

        def report(stage: str, percentage: int, message: str) -> None:
            if progress_task_id:
                deploy_task_manager.update_progress(
                    progress_task_id, stage, percentage, message
                )

        try:
            report("waiting_services", 5, f"等待应用部署完成（0/{total}）")
            for index, item in enumerate(items):
                app_name = item["app_name"]
                creds = item["credentials"]
                try:
                    status = await self._wait_task_terminal(item["task_id"])
                    if status != "completed":
                        failed.append(app_name)
                        report(
                            "provisioning",
                            10 + int(75 * (index + 1) / total),
                            f"跳过 {app_name}：部署未成功",
                        )
                        await self._write_provision_result(
                            group_id, app_name, creds, None,
                            "部署未成功，跳过账号自动配置",
                        )
                        continue

                    report(
                        "provisioning",
                        10 + int(75 * index / total),
                        f"自动配置账号：{app_name}（{index + 1}/{total}）",
                    )
                    async with async_session() as db:
                        group = await self.get_group(db, group_id)
                        entry = (group.app_configs or {}).get(app_name) or {}
                        url = entry.get("url")

                    result = await self._provision_app(
                        group_id, app_name, creds, url, item["project_name"]
                    )
                    if result is not None and not result.ok:
                        failed.append(app_name)
                except Exception:
                    failed.append(app_name)
                    logger.exception("应用 %s 账号自动配置调度失败", app_name)
                report(
                    "provisioning",
                    10 + int(75 * (index + 1) / total),
                    f"自动配置账号完成（{index + 1}/{total}）",
                )

            # 所有应用账号配置完毕后，按模板 integrations 声明把来源应用
            # （下载器/媒体服务器）自动装配进目标应用（如 MoviePilot）。
            # 注：无任何待配置应用时 _schedule_provisioning 不会调度本协程，
            # 该场景下自动装配也不触发（没有已配置应用可装配），属预期行为。
            report("wiring", 90, "装配应用集成（下载器/媒体服务器）")
            try:
                await self._wire_group(group_id)
            except Exception:
                logger.exception("实例组 %s 自动装配调度失败", group_id)

            if progress_task_id:
                if failed:
                    deploy_task_manager.complete_task(
                        progress_task_id,
                        message=(
                            f"自动配置完成，{len(failed)} 个应用未配置成功，"
                            "可在应用详情中重新装配"
                        ),
                    )
                else:
                    deploy_task_manager.complete_task(
                        progress_task_id,
                        message="账号与集成已自动配置完成",
                    )
        except Exception as exc:
            logger.exception("实例组 %s 自动配置任务异常", group_id)
            if progress_task_id:
                deploy_task_manager.fail_task(progress_task_id, str(exc))

    async def _provision_app(
        self,
        group_id: int,
        app_name: str,
        creds: dict,
        url: str,
        project_name: str,
    ) -> ProvisionResult:
        """对单个应用执行账号自动配置并落库。"""
        client = self._resolve_provision_client(app_name)
        if client is None or not url:
            message = "该应用不支持自动配置"
            await self._write_provision_result(
                group_id, app_name, creds, None, message
            )
            return ProvisionResult(ok=False, message=message)

        logs_reader = None
        host_header_port = None
        if app_name == "qbittorrent":
            logs_reader = self._make_logs_reader(project_name)
            # Host 头端口与 WebUI 监听端口不一致时 qb 5.x 会 401，
            # 需要容器内端口伪装 Host 头完成配置
            url_port = urlparse(url).port
            if url_port:
                try:
                    host_header_port = await asyncio.to_thread(
                        self._get_container_port, project_name, url_port
                    )
                except Exception:
                    logger.warning(
                        "获取 %s 容器端口失败", project_name, exc_info=True
                    )
        try:
            # provision 内部会轮询等待服务就绪，耗时可达数分钟，
            # 因此不持有数据库会话执行
            result = await client.provision(
                url=url,
                username=creds["username"],
                password=creds["password"],
                api_key=creds.get("api_key"),
                logs_reader=logs_reader,
                previous_password=creds.get("previous_password"),
                host_header_port=host_header_port,
            )
        except Exception as exc:
            logger.exception("应用 %s 账号自动配置异常", app_name)
            result = ProvisionResult(ok=False, message=f"自动配置异常: {exc}")
        await self._write_provision_result(
            group_id, app_name, creds, result, result.message
        )
        return result

    async def _reprovision_and_wire(self, group_id: int) -> None:
        """手动重跑：先补做未完成的账号自动配置，再执行自动装配。"""
        try:
            await self._reprovision_pending(group_id)
        except Exception:
            logger.exception("实例组 %s 补做账号自动配置失败", group_id)
        try:
            await self._wire_group(group_id)
        except Exception:
            logger.exception("实例组 %s 自动装配调度失败", group_id)

    async def _reprovision_pending(self, group_id: int) -> None:
        """为运行时装配类应用补做账号自动配置。

        后端进程重启会中断部署后的后台配置协程，重跑时按实例组里
        尚未配置成功的应用重新执行，已配置成功的应用跳过。
        """
        # 延迟导入：避免 app_store -> orchestration -> provisioning 的循环依赖
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.orchestration import AppInstance
        from app.services.app_store.app_service import _slugify
        from app.services.orchestration.credentials import (
            _ENV_CREDENTIAL_SPECS,
            _get_env,
        )
        from app.services.system import system_config_service

        async with async_session() as db:
            group = await self.get_group(db, group_id)
            instance_name = group.instance_name
            app_configs = dict(group.app_configs or {})
            sys_config = await system_config_service.get_or_create(db)
            default_username = (sys_config.default_admin_username or "").strip()
            unified_password = (sys_config.default_admin_password or "").strip()
            stored_configs = {
                inst.app.name: inst.config or {}
                for inst in (
                    await db.execute(
                        select(AppInstance)
                        .where(AppInstance.orchestration_group_id == group_id)
                        .options(selectinload(AppInstance.app))
                    )
                ).scalars()
                if inst.app
            }

        for app_name, entry in app_configs.items():
            if not isinstance(entry, dict) or entry.get("provisioned"):
                continue
            url = entry.get("url")
            if not url or self._resolve_provision_client(app_name) is None:
                continue
            stored_password = str(entry.get("password") or "")
            password = unified_password or stored_password
            if not password:
                continue
            creds = {
                "username": entry.get("username") or default_username or "admin",
                "password": password,
            }
            if stored_password and stored_password != password:
                creds["previous_password"] = stored_password
            # env 注入类应用（MoviePilot）的 API Token 只存在于部署配置里，
            # 补配置时沿用已有值，保证后续装配能拿到 API Key
            spec = _ENV_CREDENTIAL_SPECS.get(app_name)
            api_key = entry.get("api_key")
            if not api_key and spec:
                api_key = _get_env(
                    stored_configs.get(app_name) or {},
                    spec["env_key"],
                    spec["api_token_key"],
                )
            if api_key:
                creds["api_key"] = api_key
            await self._provision_app(
                group_id,
                app_name,
                creds,
                url,
                _slugify(f"{instance_name}-{app_name}"),
            )

    async def _write_provision_result(
        self,
        group_id: int,
        app_name: str,
        creds: dict,
        result: ProvisionResult | None,
        message: str | None,
    ) -> None:
        """把自动配置结果写入 group.app_configs[app_name] 并提交。"""
        async with async_session() as db:
            group = await self.get_group(db, group_id)
            app_configs = dict(group.app_configs or {})
            entry = dict(app_configs.get(app_name) or {})
            if result is not None and result.ok:
                entry.pop("provision_error", None)
                entry["auth_type"] = "basic"
                # 部分应用会改写登录名（如 Komga 使用邮箱），以客户端返回为准
                entry["username"] = result.username or creds["username"]
                entry["password"] = creds["password"]
                if result.api_key:
                    entry["api_key"] = result.api_key
                entry["provisioned"] = True
            else:
                entry.pop("provisioned", None)
                entry["provision_error"] = message or "自动配置失败"
            app_configs[app_name] = entry
            group.app_configs = app_configs
            await db.commit()

    def _resolve_app_client(self, app_name: str):
        """按应用名获取客户端实例，emby 复用 jellyfin 客户端。"""
        try:
            client_cls = get_client(app_name)
        except APIException:
            if app_name != "emby":
                return None
            try:
                client_cls = get_client("jellyfin")
            except APIException:
                return None
        return client_cls()

    def _resolve_provision_client(self, app_name: str):
        """按应用名获取支持自动配置的客户端实例。"""
        client = self._resolve_app_client(app_name)
        return client if client is not None and client.supports_provision else None

    @staticmethod
    def _get_project_container(project_name: str):
        """按 Compose 项目名定位主容器（容器名与项目名一致，否则按标签兜底）。"""
        client = docker_manager._client
        if client is None:
            raise RuntimeError("Docker 不可用")
        try:
            return client.containers.get(project_name)
        except docker.errors.NotFound:
            containers = client.containers.list(
                all=True,
                filters={"label": f"com.docker.compose.project={project_name}"},
            )
            if not containers:
                raise
            return containers[0]

    def _make_logs_reader(self, project_name: str):
        """构造读取 Compose 项目主容器日志的异步回调。"""

        async def read() -> str:
            def _read() -> str:
                container = self._get_project_container(project_name)
                return container.logs(tail=1000).decode("utf-8", errors="replace")

            return await asyncio.to_thread(_read)

        return read

    def _get_container_port(self, project_name: str, host_port: int) -> int | None:
        """查找映射到指定宿主机端口的容器内端口（Host 头伪装用）。"""

        def _lookup() -> int | None:
            container = self._get_project_container(project_name)
            ports = (container.attrs.get("NetworkSettings") or {}).get("Ports") or {}
            for container_port, bindings in ports.items():
                for binding in bindings or []:
                    if binding.get("HostPort") == str(host_port):
                        return int(container_port.split("/")[0])
            return None

        return _lookup()

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

        client = docker_manager._client
        if client is None:
            return
        try:
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
