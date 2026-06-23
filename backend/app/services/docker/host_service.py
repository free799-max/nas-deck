"""Docker 宿主机信息服务。"""

import shutil
from pathlib import Path

from app.core.exceptions import APIException
from app.services.docker import docker_common as common


class HostService(common.BaseDockerService):
    """宿主机信息服务，获取 Docker 引擎与主机资源概况。"""

    def list_directories(self, path: str) -> dict:
        """列出指定路径下的目录条目。

        仅返回目录，不返回文件；解析真实路径以防御路径遍历。
        """
        try:
            target = Path(path).expanduser().resolve()
        except Exception as exc:
            raise APIException(f"无效路径: {path}", 400) from exc

        if not target.exists():
            raise APIException(f"路径不存在: {path}", 404)
        if not target.is_dir():
            raise APIException(f"不是目录: {path}", 400)

        entries = []
        try:
            for child in sorted(target.iterdir()):
                if child.is_dir():
                    entries.append({
                        "name": child.name,
                        "path": str(child.resolve()),
                        "is_directory": True,
                    })
        except PermissionError as exc:
            raise APIException(f"无权限访问路径: {path}", 403) from exc
        except OSError as exc:
            raise APIException(f"读取路径失败: {exc}", 500) from exc

        return {
            "path": str(target),
            "entries": entries,
        }

    def get_host_info(self) -> dict | None:
        """获取 Docker 宿主机综合信息。"""
        if not self._client:
            return None
        try:
            version = self._client.version()
            info = self._client.info()

            docker_root_dir = info.get("DockerRootDir", "/var/lib/docker")
            disk_total = 0
            disk_free = 0
            disk_used = 0
            disk_usage_percent = 0.0
            try:
                usage = shutil.disk_usage(docker_root_dir)
                disk_total = usage.total
                disk_used = usage.used
                disk_free = usage.free
                if disk_total > 0:
                    disk_usage_percent = round((disk_used / disk_total) * 100, 2)
            except Exception:
                pass

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
