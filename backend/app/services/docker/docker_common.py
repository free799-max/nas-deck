"""Docker 服务公共基础设施。

集中导入 Docker SDK、time、logger 等，便于服务层统一引用和测试时打补丁。
"""

import logging
import time

import docker

logger = logging.getLogger(__name__)


class BaseDockerService:
    """Docker 服务基类，封装 Docker 客户端初始化与通用辅助方法。"""

    # 允许对容器执行的操作白名单
    _ALLOWED_ACTIONS = frozenset({"start", "stop", "restart", "remove"})

    def __init__(self):
        """初始化 Docker 客户端，失败时安全降级为 None。"""
        try:
            self._client = docker.from_env()
        except docker.errors.DockerException:
            self._client = None

    @property
    def available(self) -> bool:
        """检查 Docker 服务是否可用。"""
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    def _wait_for_status(
        self,
        container,
        target_status: str,
        timeout: float = 10.0,
        interval: float = 0.3,
        error_statuses: set[str] | None = None,
    ) -> dict:
        """等待容器达到目标状态。"""
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

        container.reload()
        state = container.attrs.get("State", {}) or {}
        status = state.get("Status", container.status)
        error = state.get("Error", "")
        message = f"等待容器状态超时，当前状态 {status}"
        if error:
            message += f": {error}"
        raise RuntimeError(message)

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
        """将 Docker 容器对象格式化为字典。"""
        state = container.attrs.get("State", {})
        status = state.get("Status", container.status)
        if "Health" in state:
            health = state["Health"].get("Status", "unknown")
        else:
            health = "unknown"

        config = container.attrs.get("Config", {}) or {}

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
            "id": container.id[:12],
            "name": container.name,
            "status": status,
            "state": self._state_summary(status),
            "health": health,
            "image": str(container.image.tags[0]) if container.image.tags else "unknown",
            "ports": ports_summary,
            "created": container.attrs.get("Created", ""),
            "labels": config.get("Labels") or {},
        }
