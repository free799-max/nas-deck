"""
Docker 客户端管理器模块。

提供对 Docker 守护进程的封装，支持以下功能：
- 查询容器列表（支持过滤条件）
- 获取单个容器详情
- 对容器执行启动、停止、重启操作
- 批量操作容器
- 创建容器
- 获取容器日志（含流式）
- 在容器内执行命令
- 检测 Docker 服务是否可用及容器健康状态

本模块在导入时会创建一个全局单例 docker_manager，供其他模块直接使用。
"""

import json
import logging
import os
import queue
import shlex
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta

import docker
import httpx

# 模块级日志器
logger = logging.getLogger(__name__)


class DockerManager:
    """Docker 容器管理器，封装 Docker SDK 的常用操作。

    通过 docker.from_env() 初始化客户端连接，所有方法内部均处理了
    Docker 不可用的情况，确保在 Docker 未安装或未启动时不会抛出异常。

    Attributes:
        _ALLOWED_ACTIONS: 允许执行的容器操作白名单，防止执行任意方法。
        _client: Docker SDK 客户端实例，连接失败时为 None。
    """

    # 允许对容器执行的操作白名单，仅限 start / stop / restart / remove
    _ALLOWED_ACTIONS = frozenset({"start", "stop", "restart", "remove"})

    def __init__(self):
        """初始化 Docker 客户端。

        尝试通过环境变量创建 Docker 客户端连接。
        如果 Docker 未安装或守护进程未启动，将捕获异常并将客户端设为 None。
        """
        try:
            self._client = docker.from_env()
        except docker.errors.DockerException:
            # Docker 不可用时，客户端置为 None，后续方法将返回安全默认值
            self._client = None

    @property
    def available(self) -> bool:
        """检查 Docker 服务是否可用。

        通过向 Docker 守护进程发送 ping 请求来验证连接状态。

        Returns:
            bool: True 表示 Docker 服务正常运行，False 表示不可用。
        """
        if not self._client:
            # 客户端未初始化，说明 Docker 不可用
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            # ping 失败，说明 Docker 守护进程异常
            return False

    def list_containers(self, filters: dict | None = None) -> list[dict]:
        """获取容器列表。

        Args:
            filters: Docker API 过滤条件字典，例如 {"status": "running"}。
                     为 None 时返回所有容器（包括已停止的）。

        Returns:
            list[dict]: 格式化后的容器信息列表，每个元素包含 id、name、status、health、image 字段。
                        Docker 不可用时返回空列表。
        """
        if not self._client:
            return []
        # all=True 表示包含所有状态的容器，不仅仅是运行中的
        containers = self._client.containers.list(all=True, filters=filters)
        return [self._format_container(c) for c in containers]

    def get_container(self, container_id: str) -> dict | None:
        """根据容器 ID 获取单个容器的详情。

        Args:
            container_id: 容器的完整 ID 或短 ID。

        Returns:
            dict | None: 格式化后的容器信息字典，容器不存在或 Docker 不可用时返回 None。
        """
        if not self._client:
            return None
        try:
            c = self._client.containers.get(container_id)
            return self._format_container(c)
        except docker.errors.NotFound:
            # 容器不存在时返回 None
            return None

    def container_action(self, container_id: str, action: str) -> dict:
        """对指定容器执行操作（启动、停止、重启、删除）。

        Args:
            container_id: 目标容器的 ID。
            action: 要执行的操作名称，必须是白名单中的操作。

        Returns:
            dict: 操作后的容器状态信息，包含 status 和 error 字段。

        Raises:
            ValueError: 当 action 不在允许的操作白名单中时抛出。
            RuntimeError: 当 Docker 服务不可用或等待状态超时/失败时抛出。
            docker.errors.NotFound: 当容器不存在时抛出。
        """
        if action not in self._ALLOWED_ACTIONS:
            # 拒绝不在白名单中的操作，防止执行任意方法
            raise ValueError(f"Action '{action}' is not allowed")
        if not self._client:
            raise RuntimeError("Docker not available")
        # 获取容器对象并动态调用对应的操作方法
        container = self._client.containers.get(container_id)
        getattr(container, action)()

        # 启动/重启需要确认容器真正进入目标状态
        if action in {"start", "restart"}:
            return self._wait_for_status(container, "running", timeout=10)

        # remove 操作后容器已不存在，直接返回无需 reload
        if action == "remove":
            return {"status": "removed", "error": ""}

        # stop 等其他操作立即返回当前状态
        container.reload()
        state = container.attrs.get("State", {}) or {}
        return {
            "status": state.get("Status", container.status),
            "error": state.get("Error", ""),
        }

    def _wait_for_status(
        self,
        container,
        target_status: str,
        timeout: float = 10.0,
        interval: float = 0.3,
        error_statuses: set[str] | None = None,
    ) -> dict:
        """等待容器达到目标状态。

        通过周期性 reload 容器属性检查 State.Status，直到达到目标状态、
        进入错误状态或超时。

        Args:
            container: Docker SDK 容器对象。
            target_status: 目标状态，例如 "running"。
            timeout: 最长等待时间（秒）。
            interval: 检查间隔（秒）。
            error_statuses: 视为失败的中间状态集合，默认包含 "dead"。

        Returns:
            dict: 最终状态字典，包含 status 和 error 字段。

        Raises:
            RuntimeError: 超时或进入错误状态时抛出，附带容器错误信息。
        """
        error_statuses = error_statuses or {"dead"}
        deadline = time.time() + timeout
        while time.time() < deadline:
            container.reload()
            state = container.attrs.get("State", {}) or {}
            status = state.get("Status", container.status)
            error = state.get("Error", "")
            if status == target_status:
                return {"status": status, "error": error}
            if status in error_statuses:
                message = f"容器进入错误状态 {status}"
                if error:
                    message += f": {error}"
                raise RuntimeError(message)
            time.sleep(interval)

        # 超时：再读一次状态，构造错误信息
        container.reload()
        state = container.attrs.get("State", {}) or {}
        status = state.get("Status", container.status)
        error = state.get("Error", "")
        message = f"等待容器状态超时，当前状态 {status}"
        if error:
            message += f": {error}"
        raise RuntimeError(message)

    def create_container(self, request: dict) -> dict:
        """根据请求参数创建容器。

        Args:
            request: 创建容器请求字典，字段与 ContainerCreateRequest 对应。

        Returns:
            dict: 格式化后的容器信息字典。

        Raises:
            RuntimeError: 当 Docker 服务不可用时抛出。
            docker.errors.ImageNotFound: 当镜像不存在时抛出。
            docker.errors.APIError: 当创建失败时抛出。
        """
        if not self._client:
            raise RuntimeError("Docker not available")

        # 处理端口映射："80/tcp" -> "8080" 或 "127.0.0.1:8080"
        ports = {}
        for mapping in request.get("ports") or []:
            container_port = mapping.get("container", "").strip()
            host = mapping.get("host", "").strip()
            if container_port and host:
                ports[container_port] = host

        # 处理卷挂载
        volumes = {}
        for mount in request.get("volumes") or []:
            host_path = mount.get("host", "").strip()
            container_path = mount.get("container", "").strip()
            mode = mount.get("mode", "rw")
            if host_path and container_path:
                volumes[host_path] = {"bind": container_path, "mode": mode}

        # 处理环境变量
        environment = [
            f"{item.get('key', '')}={item.get('value', '')}"
            for item in request.get("environment") or []
            if item.get("key") is not None
        ]

        # 处理标签
        labels = {
            item.get("key", ""): item.get("value", "")
            for item in request.get("labels") or []
            if item.get("key") is not None
        }

        # 拆分命令和入口点
        command = shlex.split(request["command"]) if request.get("command") else None
        entrypoint = shlex.split(request["entrypoint"]) if request.get("entrypoint") else None

        # 重启策略
        restart_policy = {"Name": request.get("restart_policy", "no")}

        create_kwargs = {
            "image": request["image"],
            "command": command,
            "entrypoint": entrypoint,
            "ports": ports or None,
            "volumes": volumes or None,
            "environment": environment or None,
            "labels": labels or None,
            "restart_policy": restart_policy,
            "detach": True,
        }

        name = request.get("name")
        if name:
            create_kwargs["name"] = name

        network = request.get("network")
        if network:
            create_kwargs["network"] = network

        # 过滤掉 None 值，避免 Docker SDK 报错
        create_kwargs = {k: v for k, v in create_kwargs.items() if v is not None}

        container = self._client.containers.create(**create_kwargs)
        if request.get("auto_start", True):
            container.start()
            # 确认容器真正进入运行状态，避免返回虚假成功
            self._wait_for_status(container, "running", timeout=10)
        return self._format_container(container)

    def batch_container_action(self, ids: list[str], action: str) -> dict:
        """批量对容器执行操作。

        Args:
            ids: 容器 ID 列表。
            action: 要执行的操作，必须是 "start"、"stop"、"restart" 或 "remove"。

        Returns:
            dict: 包含 succeeded 和 failed 两个列表的结果。

        Raises:
            ValueError: 当 action 不在白名单中时抛出。
            RuntimeError: 当 Docker 服务不可用时抛出。
        """
        if action not in self._ALLOWED_ACTIONS:
            raise ValueError(f"Action '{action}' is not allowed")
        if not self._client:
            raise RuntimeError("Docker not available")

        succeeded = []
        failed = []
        for cid in ids:
            try:
                container = self._client.containers.get(cid)
                if action == "remove":
                    container.remove(force=True)
                else:
                    getattr(container, action)()
                    # 批量启动/重启同样需要确认容器真正进入目标状态
                    if action in {"start", "restart"}:
                        self._wait_for_status(container, "running", timeout=10)
                succeeded.append(cid)
            except Exception as e:
                failed.append({"id": cid, "reason": str(e)})
        return {"succeeded": succeeded, "failed": failed}

    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """获取容器的最近日志。

        Args:
            container_id: 目标容器的 ID。
            tail: 获取最近 N 条日志，默认为 100 条。

        Returns:
            str: 容器日志文本内容。容器不存在或 Docker 不可用时返回空字符串。
        """
        if not self._client:
            return ""
        try:
            container = self._client.containers.get(container_id)
        except docker.errors.NotFound:
            return ""
        # Docker SDK 返回的是 bytes 类型，需解码为字符串
        return container.logs(tail=tail).decode("utf-8", errors="replace")

    def get_container_status(self, container_id: str) -> dict | None:
        """获取容器实时状态摘要。

        Args:
            container_id: 目标容器的 ID。

        Returns:
            dict | None: 包含 id、name、status、state 的字典；容器不存在或 Docker 不可用时返回 None。
        """
        if not self._client:
            return None
        try:
            container = self._client.containers.get(container_id)
            # reload 确保读取到最新状态，避免缓存 attrs 滞后
            container.reload()
        except docker.errors.NotFound:
            return None

        state = container.attrs.get("State", {}) or {}
        status = state.get("Status", container.status)
        return {
            "id": container.id[:12],
            "name": container.name,
            "status": status,
            "state": self._state_summary(status),
        }

    def stream_container_logs(
        self,
        container_id: str,
        tail: int = 100,
        follow: bool = True,
        timestamps: bool = True,
    ):
        """流式获取容器日志。

        Args:
            container_id: 目标容器的 ID。
            tail: 返回最后 N 行日志，默认为 100 行。
            follow: 是否持续跟踪新日志。
            timestamps: 是否包含时间戳。

        Yields:
            str: 单条日志行。

        Raises:
            RuntimeError: 当 Docker 服务不可用时抛出。
            docker.errors.NotFound: 当容器不存在时抛出。
        """
        if not self._client:
            raise RuntimeError("Docker not available")
        container = self._client.containers.get(container_id)
        for line in container.logs(
            stdout=True,
            stderr=True,
            stream=True,
            follow=follow,
            tail=tail,
            timestamps=timestamps,
        ):
            yield line.decode("utf-8", errors="replace")

    def get_container_detail(self, container_id: str) -> dict | None:
        """获取容器完整详情。

        Args:
            container_id: 目标容器的 ID。

        Returns:
            dict | None: 容器详情字典，容器不存在或 Docker 不可用时返回 None。
        """
        if not self._client:
            return None
        try:
            container = self._client.containers.get(container_id)
        except docker.errors.NotFound:
            return None

        attrs = container.attrs
        config = attrs.get("Config", {}) or {}
        state = attrs.get("State", {}) or {}
        host_config = attrs.get("HostConfig", {}) or {}
        network_settings = attrs.get("NetworkSettings", {}) or {}

        # 命令和入口点
        command = config.get("Cmd") or None
        entrypoint = config.get("Entrypoint") or None

        # 端口绑定
        ports = []
        port_bindings = network_settings.get("Ports") or {}
        for container_port, bindings in port_bindings.items():
            if isinstance(bindings, list):
                for binding in bindings:
                    ports.append({
                        "container_port": container_port,
                        "host_ip": binding.get("HostIp", ""),
                        "host_port": binding.get("HostPort", ""),
                    })
            else:
                ports.append({
                    "container_port": container_port,
                    "host_ip": "",
                    "host_port": "",
                })

        # 挂载
        mounts = []
        for mount in attrs.get("Mounts") or []:
            mounts.append({
                "type": mount.get("Type", "bind"),
                "source": mount.get("Source", ""),
                "destination": mount.get("Destination", ""),
                "mode": mount.get("Mode", "rw"),
                "rw": mount.get("RW", True),
            })

        # 网络信息
        networks = []
        network_mode = host_config.get("NetworkMode", "default")
        networks_config = network_settings.get("Networks") or {}
        for net_name, net_info in networks_config.items():
            networks.append({
                "name": net_name,
                "ip_address": net_info.get("IPAddress", ""),
                "gateway": net_info.get("Gateway", ""),
                "mac_address": net_info.get("MacAddress", ""),
            })

        # 重启策略
        restart_policy = host_config.get("RestartPolicy", {}) or {}
        restart_policy_name = restart_policy.get("Name", "no")

        # 状态摘要
        status = state.get("Status", container.status)
        health = "unknown"
        if "Health" in state:
            health = state["Health"].get("Status", "unknown")

        return {
            "id": container.id[:12],
            "name": container.name,
            "image": str(container.image.tags[0]) if container.image.tags else "unknown",
            "status": status,
            "state": self._state_summary(status),
            "health": health,
            "command": command,
            "entrypoint": entrypoint,
            "env": config.get("Env") or None,
            "working_dir": config.get("WorkingDir") or None,
            "user": config.get("User") or None,
            "labels": config.get("Labels") or None,
            "ports": ports,
            "mounts": mounts,
            "networks": networks,
            "restart_policy": restart_policy_name,
            "network_mode": network_mode,
            "privileged": host_config.get("Privileged", False),
            "created": attrs.get("Created", ""),
            "started_at": state.get("StartedAt", ""),
            "finished_at": state.get("FinishedAt", ""),
            "exit_code": state.get("ExitCode", 0),
            "error": state.get("Error", ""),
        }

    def exec_container(
        self,
        container_id: str,
        command: str,
        workdir: str | None = None,
        user: str | None = None,
        environment: list[dict] | None = None,
    ) -> tuple[int, str]:
        """在容器内执行命令。

        Args:
            container_id: 目标容器的 ID。
            command: 要执行的命令字符串。
            workdir: 工作目录（可选）。
            user: 执行用户（可选）。
            environment: 额外环境变量列表（可选）。

        Returns:
            tuple[int, str]: (退出码, 输出内容)。

        Raises:
            RuntimeError: 当 Docker 服务不可用时抛出。
            docker.errors.NotFound: 当容器不存在时抛出。
        """
        if not self._client:
            raise RuntimeError("Docker not available")
        container = self._client.containers.get(container_id)
        cmd_list = shlex.split(command)
        env_list = [
            f"{item.get('key', '')}={item.get('value', '')}"
            for item in environment or []
            if item.get("key") is not None
        ]
        exec_kwargs = {
            "stdout": True,
            "stderr": True,
            "stream": True,
        }
        if workdir:
            exec_kwargs["workdir"] = workdir
        if user:
            exec_kwargs["user"] = user
        if env_list:
            exec_kwargs["environment"] = env_list

        result = container.exec_run(cmd_list, **exec_kwargs)
        output_chunks = []
        for chunk in result.output:
            output_chunks.append(chunk.decode("utf-8", errors="replace"))
        return result.exit_code, "".join(output_chunks)

    def exec_container_interactive(
        self,
        container_id: str,
        command: list[str],
        workdir: str | None = None,
        user: str | None = None,
        environment: list[dict] | None = None,
        tty: bool = True,
    ) -> tuple[str, object]:
        """在容器内创建交互式 exec 会话。

        通过 Docker SDK 的 exec_create + exec_start(socket=True) 获得一个可读写的 socket，
        用于 WebSocket 双向转发，实现类似 `docker exec -it` 的交互体验。

        Args:
            container_id: 目标容器的 ID。
            command: 要执行的命令列表，例如 ["/bin/sh"]。
            workdir: 工作目录（可选）。
            user: 执行用户（可选）。
            environment: 额外环境变量列表（可选）。
            tty: 是否分配伪终端，默认 True。

        Returns:
            tuple[str, object]: (exec_id, socket)。

        Raises:
            RuntimeError: 当 Docker 服务不可用时抛出。
            docker.errors.NotFound: 当容器不存在时抛出。
        """
        if not self._client:
            raise RuntimeError("Docker not available")
        container = self._client.containers.get(container_id)
        env_list = [
            f"{item.get('key', '')}={item.get('value', '')}"
            for item in environment or []
            if item.get("key") is not None
        ]
        exec_kwargs = {
            "stdin": True,
            "stdout": True,
            "stderr": True,
            "tty": tty,
        }
        if workdir:
            exec_kwargs["workdir"] = workdir
        if user:
            exec_kwargs["user"] = user
        if env_list:
            exec_kwargs["environment"] = env_list

        exec_id = self._client.api.exec_create(container.id, command, **exec_kwargs)
        socket = self._client.api.exec_start(exec_id, socket=True, tty=tty)
        return exec_id, socket

    def _state_summary(self, status: str) -> str:
        """根据 Docker 状态返回中文摘要。"""
        mapping = {
            "running": "运行中",
            "exited": "已停止",
            "paused": "已暂停",
            "restarting": "重启中",
            "dead": "已死亡",
            "created": "已创建",
        }
        return mapping.get(status, status)

    def _format_container(self, container) -> dict:
        """将 Docker 容器对象格式化为字典。

        提取容器的基本信息和健康检查状态。

        Args:
            container: Docker SDK 的 Container 对象。

        Returns:
            dict: 包含 id（短 ID）、name、status、state、health、image、ports、created 的字典。
        """
        # 默认健康状态为 unknown
        health = "unknown"
        # 从容器属性中提取健康检查状态
        state = container.attrs.get("State", {})
        status = state.get("Status", container.status)
        if "Health" in state:
            health = state["Health"].get("Status", "unknown")

        config = container.attrs.get("Config", {}) or {}

        # 端口映射摘要
        ports_summary = ""
        network_settings = container.attrs.get("NetworkSettings", {}) or {}
        port_bindings = network_settings.get("Ports") or {}
        parts = []
        for container_port, bindings in port_bindings.items():
            if isinstance(bindings, list):
                for binding in bindings:
                    host_ip = binding.get("HostIp", "0.0.0.0")
                    host_port = binding.get("HostPort", "")
                    if host_ip == "0.0.0.0":
                        parts.append(f"{host_port}:{container_port}")
                    else:
                        parts.append(f"{host_ip}:{host_port}:{container_port}")
        ports_summary = ", ".join(parts)

        return {
            "id": container.id[:12],  # 使用 12 位短 ID，与 docker 命令行一致
            "name": container.name,
            "status": status,
            "state": self._state_summary(status),
            "health": health,
            "image": str(container.image.tags[0]) if container.image.tags else "unknown",
            "ports": ports_summary,
            "created": container.attrs.get("Created", ""),
            "labels": config.get("Labels") or {},
        }

    def get_host_info(self) -> dict | None:
        """获取 Docker 宿主机综合信息。

        通过 Docker SDK 获取 Docker 引擎版本信息、系统信息、磁盘使用情况和网络列表。
        即使后端部署在 Docker 容器内，Docker SDK 调用守护进程返回的也是宿主机视角的数据。

        Returns:
            dict | None: 包含 hostname、os、arch、kernel_version、docker_version、
                        resources、stats、storage_driver、docker_root_dir、networks 的字典。
                        Docker 不可用时返回 None。
        """
        if not self._client:
            return None
        try:
            # Docker 版本信息
            version = self._client.version()
            # Docker 系统信息
            info = self._client.info()

            # 磁盘信息：基于 Docker 根目录所在文件系统
            docker_root_dir = info.get("DockerRootDir", "/var/lib/docker")
            disk_total = 0
            disk_free = 0
            disk_used = 0
            disk_usage_percent = 0.0
            try:
                # 优先使用跨平台的 shutil.disk_usage（Windows / Linux / macOS 均支持）
                usage = shutil.disk_usage(docker_root_dir)
                disk_total = usage.total
                disk_used = usage.used
                disk_free = usage.free
                if disk_total > 0:
                    disk_usage_percent = round((disk_used / disk_total) * 100, 2)
            except Exception:
                # 路径不存在或平台不支持时安全降级
                pass

            # Docker 网络列表
            networks = []
            for net in self._client.networks.list():
                networks.append({
                    "id": net.id[:12],
                    "name": net.name,
                    "driver": net.attrs.get("Driver", "bridge"),
                    "scope": net.attrs.get("Scope", "local"),
                })

            return {
                "hostname": info.get("Name", "unknown"),
                "os": version.get("Os", "unknown"),
                "arch": version.get("Arch", "unknown"),
                "kernel_version": version.get("KernelVersion", "unknown"),
                "docker_version": {
                    "version": version.get("Version", "unknown"),
                    "api_version": version.get("ApiVersion", "unknown"),
                    "go_version": version.get("GoVersion", "unknown"),
                    "os": version.get("Os", "unknown"),
                    "arch": version.get("Arch", "unknown"),
                    "kernel_version": version.get("KernelVersion", "unknown"),
                    "build_time": version.get("BuildTime", "unknown"),
                },
                "resources": {
                    "cpu_cores": info.get("NCPU", 0),
                    "memory_total": info.get("MemTotal", 0),
                    "disk_total": disk_total,
                    "disk_used": disk_used,
                    "disk_free": disk_free,
                    "disk_usage_percent": disk_usage_percent,
                },
                "stats": {
                    "containers_total": info.get("Containers", 0),
                    "containers_running": info.get("ContainersRunning", 0),
                    "containers_paused": info.get("ContainersPaused", 0),
                    "containers_stopped": info.get("ContainersStopped", 0),
                    "images": info.get("Images", 0),
                },
                "storage_driver": info.get("Driver", "unknown"),
                "docker_root_dir": docker_root_dir,
                "networks": networks,
            }
        except Exception:
            return None

    def list_images(self) -> list[dict]:
        """获取本地镜像列表（扁平化，每行对应一个 tag）。

        Returns:
            list[dict]: 格式化后的镜像信息列表，每行包含 id、image_id、name、tag、
                        full_tag、size、created、containers。
                        Docker 不可用时返回空列表。
        """
        if not self._client:
            return []
        images = self._client.images.list()
        # 统计每个镜像被多少个容器使用
        containers = self._client.containers.list(all=True)
        image_usage = {}
        for c in containers:
            img_id = c.image.id
            image_usage[img_id] = image_usage.get(img_id, 0) + 1

        result = []
        for img in images:
            attrs = img.attrs
            repo_tags = attrs.get("RepoTags") or []
            if not repo_tags:
                repo_tags = ["<none>:<none>"]

            full_id = img.id
            short_id = full_id.split(":")[-1][:12] if ":" in full_id else full_id[:12]
            container_count = image_usage.get(full_id, 0)

            for tag_str in repo_tags:
                # 按最后一个 ":" 分割为 name 和 tag
                if ":" in tag_str:
                    name, tag = tag_str.rsplit(":", 1)
                else:
                    name, tag = tag_str, "<none>"
                result.append({
                    "id": short_id,
                    "image_id": full_id,
                    "name": name,
                    "tag": tag,
                    "full_tag": tag_str,
                    "size": attrs.get("Size", 0),
                    "created": attrs.get("Created", ""),
                    "containers": container_count,
                })
        return result

    def get_image_detail(self, image_id: str) -> dict | None:
        """获取镜像完整元数据。

        Args:
            image_id: 镜像完整 ID（sha256:...）或短 ID。

        Returns:
            dict | None: 镜像元数据字典，镜像不存在或 Docker 不可用时返回 None。
        """
        if not self._client:
            return None
        try:
            image = self._client.images.get(image_id)
            attrs = image.attrs
            config = attrs.get("Config", {}) or {}
            rootfs = attrs.get("RootFS", {}) or {}
            history = attrs.get("History", []) or []

            # 提取暴露端口
            exposed_ports = []
            ports = config.get("ExposedPorts", {})
            if ports:
                exposed_ports = list(ports.keys())

            # 提取卷
            volumes = []
            vols = config.get("Volumes", {})
            if vols:
                volumes = list(vols.keys())

            # 提取构建历史命令
            history_cmds = []
            for h in history:
                created_by = h.get("CreatedBy", "")
                if created_by:
                    history_cmds.append(created_by)

            # 提取层
            layers = rootfs.get("Layers", []) or []

            # 名称和标签取第一个 RepoTag
            repo_tags = attrs.get("RepoTags") or ["<none>:<none>"]
            first_tag = repo_tags[0]
            if ":" in first_tag:
                name, tag = first_tag.rsplit(":", 1)
            else:
                name, tag = first_tag, "<none>"

            # 父镜像与 Docker 版本
            parent = attrs.get("Parent") or None
            docker_version = attrs.get("DockerVersion") or None
            architecture = attrs.get("Architecture", "")
            os_value = attrs.get("Os", "")
            build = None
            if docker_version and os_value and architecture:
                build = f"Docker {docker_version} on {os_value}, {architecture}"

            # 通过 image.history() 获取带 size 的层信息
            layers_table = []
            try:
                for i, layer in enumerate(image.history()):
                    created_by = (layer.get("CreatedBy", "") or "").strip()
                    if not created_by:
                        continue
                    layers_table.append({
                        "order": i,
                        "size": layer.get("Size", 0) or 0,
                        "layer": created_by,
                    })
            except Exception:
                # 部分镜像格式可能不支持 history()，安全降级
                layers_table = []

            return {
                "id": attrs.get("Id", ""),
                "name": name,
                "tag": tag,
                "full_tag": first_tag,
                "size": attrs.get("Size", 0),
                "created": attrs.get("Created", ""),
                "architecture": architecture,
                "os": os_value,
                "cmd": config.get("Cmd"),
                "entrypoint": config.get("Entrypoint"),
                "env": config.get("Env"),
                "exposed_ports": exposed_ports or None,
                "volumes": volumes or None,
                "working_dir": config.get("WorkingDir") or None,
                "user": config.get("User") or None,
                "labels": config.get("Labels") or None,
                "layers": layers or None,
                "history": history_cmds or None,
                "parent": parent,
                "docker_version": docker_version,
                "build": build,
                "layers_table": layers_table or None,
            }
        except docker.errors.ImageNotFound:
            return None
        except Exception:
            return None

    def prune_unused_images(self) -> dict:
        """移除所有未使用的镜像（包括有标签但无容器引用的镜像）。

        Returns:
            dict: 包含 deleted（被删除的镜像标签列表）和
                  space_reclaimed（释放空间字节数）的字典。

        Raises:
            RuntimeError: Docker 不可用时抛出。
        """
        if not self._client:
            raise RuntimeError("Docker not available")
        result = self._client.images.prune(filters={"dangling": False})
        # Docker 返回的 ImagesDeleted 同时包含"Untagged"（镜像标签）和"Deleted"（层摘要）。
        # 用户感知的"镜像数量"应以标签为准，层摘要不计入镜像数。
        deleted_tags = [
            item["Untagged"]
            for item in result.get("ImagesDeleted", [])
            if "Untagged" in item
        ]
        return {
            "deleted": deleted_tags,
            "space_reclaimed": result.get("SpaceReclaimed", 0),
        }

    def remove_image(self, image_id: str, force: bool = False):
        """删除指定镜像。

        Args:
            image_id: 镜像 ID（短 ID 或完整 ID）或标签。
            force: 是否强制删除（包括有容器引用的镜像）。

        Raises:
            docker.errors.ImageNotFound: 镜像不存在时抛出。
            docker.errors.APIError: 删除失败时抛出。
            RuntimeError: Docker 不可用时抛出。
        """
        if not self._client:
            raise RuntimeError("Docker not available")
        self._client.images.remove(image_id, force=force)

    def remove_images(self, image_ids: list[str], force: bool = False) -> dict:
        """批量删除镜像。

        Args:
            image_ids: 镜像 ID 列表。
            force: 是否强制删除。

        Returns:
            dict: 包含 deleted 和 failed 两个列表的结果字典。

        Raises:
            RuntimeError: Docker 不可用时抛出。
        """
        if not self._client:
            raise RuntimeError("Docker not available")
        deleted = []
        failed = []
        for image_id in image_ids:
            try:
                self._client.images.remove(image_id, force=force)
                deleted.append(image_id)
            except docker.errors.ImageNotFound:
                failed.append({"id": image_id, "reason": "镜像不存在"})
            except docker.errors.APIError as e:
                failed.append({"id": image_id, "reason": str(e)})
        return {"deleted": deleted, "failed": failed}

    def search_images(
        self,
        query: str,
        page: int = 1,
        api_url: str | None = None,
        mirror_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> dict:
        """搜索镜像。

        当提供 api_url 时，调用自定义镜像搜索 API；否则通过 Docker Hub v2 API 搜索。
        支持 Basic Auth 认证，主地址失败时可 fallback 到镜像地址。

        第三方 API 调用格式: {api_url}?search={query}
        Docker Hub 格式: {api_url}?query={query}&page_size=20&page={page}

        Args:
            query: 搜索关键词。
            page: 页码，从 1 开始。
            api_url: 自定义镜像搜索 API 主地址，为 None 时使用 Docker Hub。
            mirror_url: 镜像搜索 API 镜像地址，主地址失败时作为 fallback。
            username: 认证用户名。
            password: 认证密码。

        Returns:
            dict: 分页结果，包含 total、page、page_size、results。
        """
        import httpx
        import urllib.parse

        if not query.strip():
            return {"total": 0, "page": page, "page_size": 20, "results": []}

        auth = (username, password) if username and password else None
        page_size = 20

        def _parse_item(r: dict, field_map: dict[str, str]) -> dict:
            """解析单条搜索结果，通过字段映射适配不同 API 格式。"""
            def _get(key: str, default=None):
                # 优先使用映射后的字段名，回退到通用字段名
                mapped = field_map.get(key, key)
                return r.get(mapped, r.get(key, default))

            return {
                "name": _get("name", ""),
                "description": _get("description", ""),
                "star_count": _get("star_count", 0),
                "pull_count": _get("pull_count", 0),
                "official": _get("official", False),
                "is_automated": _get("is_automated", False),
            }

        def _do_search(url: str, is_docker_hub: bool = False) -> dict:
            """执行单次搜索请求，返回分页结果；失败时抛出异常并记录日志。"""
            try:
                logger.info("镜像搜索请求: %s", url)
                resp = httpx.get(url, timeout=10, auth=auth)
                resp.raise_for_status()
                data = resp.json()
                if is_docker_hub:
                    results = data.get("results", [])
                    return {
                        "total": data.get("count", len(results)),
                        "page": page,
                        "page_size": page_size,
                        "results": [_parse_item(r, {"name": "repo_name", "description": "short_description", "official": "is_official"}) for r in results],
                    }
                # 适配两种常见返回格式: 直接列表 或 嵌套在 results 中
                if isinstance(data, list):
                    return {
                        "total": len(data),
                        "page": page,
                        "page_size": page_size,
                        "results": [_parse_item(r, {}) for r in data],
                    }
                results = data.get("results", [])
                return {
                    "total": data.get("count", data.get("total", len(results))),
                    "page": data.get("page", page),
                    "page_size": data.get("page_size", page_size),
                    "results": [_parse_item(r, {}) for r in results],
                }
            except httpx.HTTPStatusError as e:
                msg = f"镜像搜索接口返回错误: {e.response.status_code} {e.response.reason_phrase} ({url})"
                logger.error(msg)
                raise RuntimeError(msg) from e
            except httpx.RequestError as e:
                msg = f"镜像搜索接口请求失败: {e.__class__.__name__}: {e} ({url})"
                logger.error(msg)
                raise RuntimeError(msg) from e
            except Exception as e:
                msg = f"镜像搜索接口解析失败: {e.__class__.__name__}: {e} ({url})"
                logger.error(msg)
                raise RuntimeError(msg) from e

        def _build_search_url(base_url: str, is_docker_hub: bool) -> str:
            """构造搜索 URL。"""
            base = base_url.rstrip("/")
            if is_docker_hub:
                # 若 base_url 已包含完整 API 路径则直接复用，否则追加
                if not base.lower().endswith("/v2/search/repositories"):
                    base += "/v2/search/repositories"
                return (
                    base
                    + "?query="
                    + urllib.parse.quote(query.strip())
                    + f"&page_size={page_size}"
                    + f"&page={page}"
                )
            return base + "?search=" + urllib.parse.quote(query.strip())

        def _is_docker_hub_format(url: str) -> bool:
            """判断 URL 是否为 Docker Hub 格式（域名或完整 API 路径）。"""
            url_lower = url.lower().rstrip("/")
            return (
                url_lower == "https://hub.docker.com"
                or url_lower == "https://registry.hub.docker.com"
                or url_lower.endswith("/v2/search/repositories")
                or url_lower.startswith("https://hub.docker.com")
                or url_lower.startswith("https://registry.hub.docker.com")
            )

        def _resolve_api_url(config_url: str | None) -> str | None:
            """将简化的 Docker Hub URL 解析为完整 API 地址。"""
            if not config_url:
                return None
            url = config_url.strip()
            if url.rstrip("/").lower() in ("https://hub.docker.com", "https://registry.hub.docker.com"):
                return "https://hub.docker.com/v2/search/repositories"
            return url

        resolved_api = _resolve_api_url(api_url)
        resolved_mirror = _resolve_api_url(mirror_url)
        errors: list[str] = []

        if resolved_api:
            is_hub = _is_docker_hub_format(resolved_api)
            url = _build_search_url(resolved_api, is_hub)
            try:
                return _do_search(url, is_docker_hub=is_hub)
            except RuntimeError as e:
                errors.append(str(e))
            # 主地址失败，尝试镜像地址
            if resolved_mirror:
                is_hub = _is_docker_hub_format(resolved_mirror)
                url = _build_search_url(resolved_mirror, is_hub)
                try:
                    return _do_search(url, is_docker_hub=is_hub)
                except RuntimeError as e:
                    errors.append(str(e))
            raise RuntimeError("镜像搜索全部失败: " + "; ".join(errors))

        # 默认使用 Docker Hub v2 API
        default_url = "https://hub.docker.com/v2/search/repositories"
        url = _build_search_url(default_url, is_docker_hub=True)
        try:
            return _do_search(url, is_docker_hub=True)
        except RuntimeError as e:
            raise RuntimeError("镜像搜索失败: " + str(e)) from e

    def pull_image(self, image: str):
        """拉取指定镜像。

        Args:
            image: 镜像名称（含可选标签，如 "nginx:latest"）。

        Raises:
            docker.errors.ImageNotFound: 镜像不存在时抛出。
            docker.errors.APIError: 拉取失败时抛出。
            RuntimeError: Docker 不可用时抛出。
        """
        if not self._client:
            raise RuntimeError("Docker not available")
        self._client.images.pull(image)

    def get_image_tags(self, image: str) -> list[dict]:
        """获取指定镜像的可用标签列表。

        通过 Docker Hub API 查询镜像的所有可用 tags。
        对于非 library/ 前缀的官方镜像，自动添加 library/ 前缀。

        Args:
            image: 镜像名称（不含标签，如 "nginx"）。

        Returns:
            list[dict]: 标签信息列表，每个元素包含 name、last_updated、size、digest。
                        查询失败时返回空列表。
        """
        # 构造 Docker Hub API 路径
        repo = image.strip()
        if "/" not in repo:
            repo = f"library/{repo}"

        url = f"https://hub.docker.com/v2/repositories/{repo}/tags/?page_size=100"
        try:
            resp = httpx.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            tags = []
            for r in results:
                tags.append({
                    "name": r.get("name", ""),
                    "last_updated": r.get("last_updated", ""),
                    "size": r.get("full_size", 0),
                    "digest": r.get("digest", ""),
                })
            return tags
        except Exception:
            return []

    def pull_image_async(self, image: str, task_id: str, task_manager):
        """在后台线程中流式拉取指定镜像，并报告进度。

        解析 Docker SDK 流式输出，计算下载速度、中文状态映射、
        每层独立进度和总体进度汇总。

        Args:
            image: 镜像名称（含标签，如 "nginx:latest"）。
            task_id: 任务唯一标识。
            task_manager: ImagePullTaskManager 实例，用于更新进度状态。

        Raises:
            RuntimeError: Docker 不可用时抛出。
        """
        if not self._client:
            task_manager.fail_task(task_id, "Docker not available")
            raise RuntimeError("Docker not available")

        # 中文状态映射表
        STATUS_MAP = {
            "Pulling from": "拉取中",
            "Pulling fs layer": "准备下载",
            "Waiting": "等待中",
            "Downloading": "下载中",
            "Download complete": "下载完成",
            "Verifying Checksum": "验证中",
            "Pull complete": "已完成",
            "Already exists": "已存在",
            "Layer already exists": "已存在",
            "Extracting": "解压中",
            "Pulling manifest": "获取清单",
        }

        def _format_bytes(b: int) -> str:
            if b == 0:
                return "0 B"
            k = 1024
            sizes = ["B", "KB", "MB", "GB", "TB"]
            i = min(len(sizes) - 1, int(__import__("math").log(b) / __import__("math").log(k)))
            return f"{b / (k ** i):.1f} {sizes[i]}"

        def _map_status(status: str) -> str:
            for key, value in STATUS_MAP.items():
                if key in status:
                    return value
            return status

        try:
            stream = self._client.api.pull(image, stream=True, decode=True)
            layers = {}  # layer_id -> { status, current, total, last_current, last_time, speed }
            last_progress_time = time.time()
            last_overall_percentage = 0  # 单调递增保护：记录上次报告的总百分比

            for line in stream:
                if not line:
                    continue

                status = line.get("status", "")
                layer_id = line.get("id", "")
                progress_detail = line.get("progressDetail", {}) or {}
                current = progress_detail.get("current", 0) or 0
                total = progress_detail.get("total", 0) or 0

                now = time.time()

                if layer_id:
                    if layer_id not in layers:
                        layers[layer_id] = {
                            "status": status,
                            "current": current,
                            "total": total,
                            "last_current": current,
                            "last_time": now,
                            "speed": 0,
                        }
                    else:
                        old = layers[layer_id]
                        # 计算该层下载速度
                        time_delta = now - old["last_time"]
                        if time_delta >= 0.5 and current > old["last_current"]:
                            speed = int((current - old["last_current"]) / time_delta)
                            old["speed"] = speed
                            old["last_current"] = current
                            old["last_time"] = now
                        old["status"] = status
                        old["current"] = current
                        if total > 0:
                            old["total"] = total

                # 构建每层进度详情
                layer_progress_list = []
                total_size = 0
                downloaded_size = 0
                total_speed = 0
                downloading_count = 0
                completed_layers = 0

                for lid, ldata in layers.items():
                    l_total = ldata.get("total", 0)
                    l_current = ldata.get("current", 0)
                    l_status = ldata.get("status", "")
                    l_speed = ldata.get("speed", 0)

                    # 该层百分比：已完成/已存在/下载完成的层固定为 100%
                    completed_statuses = (
                        "Pull complete",
                        "Already exists",
                        "Layer already exists",
                        "Download complete",
                    )
                    l_percentage = 0
                    if l_status in completed_statuses:
                        l_percentage = 100
                    elif l_total > 0 and l_current > 0:
                        l_percentage = int((l_current / l_total) * 100)

                    # 进度文字
                    if l_status in completed_statuses:
                        progress_text = "已完成"
                    elif l_total > 0:
                        progress_text = f"{_format_bytes(l_current)} / {_format_bytes(l_total)}"
                    else:
                        progress_text = "--"

                    layer_progress_list.append({
                        "id": lid,
                        "status": l_status,
                        "status_text": _map_status(l_status),
                        "current": l_current,
                        "total": l_total,
                        "progress_text": progress_text,
                        "percentage": l_percentage,
                        "speed": l_speed,
                    })

                    if l_status in (
                        "Pull complete",
                        "Already exists",
                        "Layer already exists",
                        "Download complete",
                    ) or l_percentage == 100:
                        completed_layers += 1

                    if l_total > 0:
                        total_size += l_total
                        downloaded_size += min(l_current, l_total)

                    if l_speed > 0:
                        total_speed += l_speed
                        downloading_count += 1

                # 总体百分比：优先按字节加权，更准确；无字节信息时回退到层平均
                total_layers = len(layers)
                byte_percentage = 0
                if total_size > 0:
                    byte_percentage = int((downloaded_size / total_size) * 100)

                layer_average_percentage = 0
                if total_layers > 0:
                    layer_percentage_sum = sum(
                        layer["percentage"] for layer in layer_progress_list
                    )
                    layer_average_percentage = int(layer_percentage_sum / total_layers)

                # 取字节加权和层平均的较大值，避免已完成层无字节信息时进度被 0 字节卡住
                calculated_percentage = max(byte_percentage, layer_average_percentage)

                # 单调递增保护：新层动态发现时可能导致计算值下降，显示进度不允许回退
                percentage = max(calculated_percentage, last_overall_percentage)
                last_overall_percentage = percentage

                # 整体状态文字
                if downloading_count > 0:
                    overall_status = f"下载中 {downloading_count} 个层"
                elif completed_layers < total_layers:
                    overall_status = "准备下载"
                else:
                    overall_status = "处理中"

                size_text = f"{_format_bytes(downloaded_size)} / {_format_bytes(total_size)}" if total_size > 0 else "--"

                progress = {
                    "total_layers": total_layers,
                    "completed_layers": completed_layers,
                    "current_layer": layer_id,
                    "percentage": min(percentage, 99),
                    "status": overall_status,
                    "speed": total_speed,
                    "total_size": total_size,
                    "downloaded_size": downloaded_size,
                    "size_text": size_text,
                    "layers": layer_progress_list,
                }

                # 节流：每 0.3 秒更新一次，避免过于频繁的 SSE 推送
                if now - last_progress_time >= 0.3:
                    task_manager.update_progress(task_id, progress)
                    last_progress_time = now

            # 拉取完成，推送最终 100% 状态
            task_manager.complete_task(task_id)
        except docker.errors.ImageNotFound:
            task_manager.fail_task(task_id, "镜像不存在")
        except docker.errors.APIError as e:
            task_manager.fail_task(task_id, f"拉取镜像失败: {e}")
        except Exception as e:
            task_manager.fail_task(task_id, f"拉取镜像失败: {e}")


class ImagePullTaskManager:
    """镜像拉取任务管理器。

    管理后台拉取任务的进度状态，支持 SSE 推送和页面切换恢复。
    任务状态存储在内存中，完成后保留 5 分钟（TTL），最大保留 50 个任务。

    Attributes:
        _tasks: 任务状态字典，key 为 task_id。
        _listeners: 每个任务的监听器队列字典，用于 SSE 推送新进度。
        _lock: 线程锁，保护 _tasks 和 _listeners。
    """

    def __init__(self, max_tasks: int = 50, ttl_seconds: int = 300, max_concurrent: int = 3, task_timeout_seconds: int = 600):
        """初始化任务管理器。

        Args:
            max_tasks: 最大保留任务数，超过时清理最早完成的任务。
            ttl_seconds: 已完成任务的保留时间（秒）。
            max_concurrent: 最大并发拉取任务数。
            task_timeout_seconds: pulling 状态任务超时时间（秒），超过自动标记失败。
        """
        self._tasks: dict[str, dict] = {}
        self._listeners: dict[str, list[queue.Queue]] = {}
        self._lock = threading.Lock()
        self._max_tasks = max_tasks
        self._ttl_seconds = ttl_seconds
        self._max_concurrent = max_concurrent
        self._task_timeout_seconds = task_timeout_seconds

    def get_running_count(self) -> int:
        """获取当前正在运行的任务数。"""
        with self._lock:
            return sum(
                1 for t in self._tasks.values()
                if t.get("status") == "pulling"
            )

    def can_start_new_task(self) -> bool:
        """检查是否可以启动新任务（未超过并发限制）。"""
        with self._lock:
            running = sum(
                1 for t in self._tasks.values()
                if t.get("status") == "pulling"
            )
            return running < self._max_concurrent

    def create_task(self, image: str) -> str:
        """创建新任务并返回 task_id。

        Args:
            image: 要拉取的镜像名称（含标签）。

        Returns:
            str: 任务唯一标识（UUID）。

        Raises:
            RuntimeError: 当并发任务数超过限制时抛出。
        """
        with self._lock:
            running = sum(
                1 for t in self._tasks.values()
                if t.get("status") == "pulling"
            )
            if running >= self._max_concurrent:
                raise RuntimeError(
                    f"并发拉取任务数已达上限（{self._max_concurrent}个），"
                    f"请等待现有任务完成后再试"
                )

        task_id = str(uuid.uuid4())
        with self._lock:
            self._cleanup_expired()
            self._tasks[task_id] = {
                "task_id": task_id,
                "image": image,
                "status": "pulling",
                "progress": {
                    "total_layers": 0,
                    "completed_layers": 0,
                    "current_layer": "",
                    "percentage": 0,
                    "status": "准备拉取",
                    "speed": 0,
                    "total_size": 0,
                    "downloaded_size": 0,
                    "size_text": "--",
                    "layers": [],
                },
                "error": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "completed_at": None,
            }
            self._listeners[task_id] = []
        return task_id

    def update_progress(self, task_id: str, progress: dict):
        """更新任务进度并通知所有监听器。

        Args:
            task_id: 任务 ID。
            progress: 进度信息字典。
        """
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["progress"] = progress
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            # 通知所有 SSE 监听器
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(progress)
                except queue.Full:
                    pass

    def complete_task(self, task_id: str):
        """标记任务为已完成。

        Args:
            task_id: 任务 ID。
        """
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["status"] = "completed"
            progress = self._tasks[task_id]["progress"]
            progress["percentage"] = 100
            progress["status"] = "拉取完成"
            progress["speed"] = 0
            # 更新所有层状态为已完成，并同步层计数
            layers = progress.get("layers", [])
            for layer in layers:
                layer["status"] = "Pull complete"
                layer["status_text"] = "已完成"
                layer["percentage"] = 100
                layer["speed"] = 0
            progress["completed_layers"] = len(layers)
            progress["total_layers"] = len(layers)
            progress["size_text"] = "--"
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            # 通知所有 SSE 监听器，嵌入状态以便前端同步
            _notify_progress = self._tasks[task_id]["progress"].copy()
            _notify_progress["_task_status"] = "completed"
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(_notify_progress)
                except queue.Full:
                    pass

    def fail_task(self, task_id: str, error: str):
        """标记任务为失败。

        Args:
            task_id: 任务 ID。
            error: 错误信息。
        """
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = error
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            # 通知所有 SSE 监听器，嵌入状态以便前端同步
            _notify_progress = self._tasks[task_id]["progress"].copy()
            _notify_progress["_task_status"] = "failed"
            _notify_progress["_error"] = error
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(_notify_progress)
                except queue.Full:
                    pass

    def _check_task_timeout(self, task: dict) -> bool:
        """检查任务是否已超时，超时时自动标记为失败。

        已超时并已通知的任务不会重复通知监听器。

        Args:
            task: 任务状态字典。

        Returns:
            bool: 是否已超时并被标记失败。
        """
        if task.get("status") != "pulling":
            return False
        # 已标记超时且已通知，避免重复推送
        if task.get("_timeout_notified"):
            return True
        updated_at = task.get("updated_at")
        if not updated_at:
            return False
        try:
            updated_dt = datetime.fromisoformat(updated_at)
            if (datetime.now() - updated_dt).total_seconds() > self._task_timeout_seconds:
                task["status"] = "failed"
                task["error"] = "拉取超时，请检查网络或镜像源配置"
                task["completed_at"] = datetime.now().isoformat()
                task["updated_at"] = datetime.now().isoformat()
                task["_timeout_notified"] = True
                # 通知所有监听器
                for q in self._listeners.get(task["task_id"], []):
                    try:
                        q.put_nowait(task["progress"])
                    except queue.Full:
                        pass
                return True
        except Exception:
            pass
        return False

    def get_task(self, task_id: str) -> dict | None:
        """获取任务状态。

        自动检测 pulling 任务是否超时，超时时标记为失败。

        Args:
            task_id: 任务 ID。

        Returns:
            dict | None: 任务状态字典，不存在时返回 None。
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                self._check_task_timeout(task)
            return task

    def register_listener(self, task_id: str) -> queue.Queue:
        """注册 SSE 监听器队列。

        Args:
            task_id: 任务 ID。

        Returns:
            queue.Queue: 用于接收进度更新的队列。
        """
        q = queue.Queue(maxsize=100)
        with self._lock:
            if task_id in self._listeners:
                self._listeners[task_id].append(q)
        return q

    def unregister_listener(self, task_id: str, q: queue.Queue):
        """注销 SSE 监听器队列。

        Args:
            task_id: 任务 ID。
            q: 要注销的队列。
        """
        with self._lock:
            if task_id in self._listeners:
                try:
                    self._listeners[task_id].remove(q)
                except ValueError:
                    pass

    def _cleanup_expired(self):
        """清理过期和超额的任务。"""
        now = datetime.now()
        expired = []
        for tid, task in self._tasks.items():
            # 检查已完成任务是否超过 TTL
            completed_at = task.get("completed_at")
            if completed_at:
                try:
                    completed_dt = datetime.fromisoformat(completed_at)
                    if (now - completed_dt).total_seconds() > self._ttl_seconds:
                        expired.append(tid)
                except Exception:
                    pass
            # 检查 pulling 任务是否超时
            elif task.get("status") == "pulling":
                if self._check_task_timeout(task):
                    expired.append(tid)

        for tid in expired:
            self._tasks.pop(tid, None)
            self._listeners.pop(tid, None)

        # 如果仍然超过最大任务数，清理最早完成的
        if len(self._tasks) > self._max_tasks:
            completed_tasks = [
                (tid, t) for tid, t in self._tasks.items()
                if t.get("completed_at")
            ]
            completed_tasks.sort(key=lambda x: x[1].get("completed_at", ""))
            to_remove = len(self._tasks) - self._max_tasks
            for tid, _ in completed_tasks[:to_remove]:
                self._tasks.pop(tid, None)
                self._listeners.pop(tid, None)


# 全局单例，供其他模块直接导入使用
docker_manager = DockerManager()
task_manager = ImagePullTaskManager()
