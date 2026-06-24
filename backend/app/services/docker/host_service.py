"""Docker 宿主机信息服务。"""

import shutil

from app.services.docker import docker_common as common
from app.services.host.filesystem_service import filesystem_service


class HostService(common.BaseDockerService):
    """宿主机信息服务，获取 Docker 引擎与主机资源概况。"""

    def list_directories(
        self,
        path: str,
        root_path: str | None = None,
    ) -> dict:
        """列出指定路径下的目录条目。

        委托给通用文件系统服务实现，保持 Docker 宿主机的 API 入口不变。
        """
        return filesystem_service.list_directories(path, root_path=root_path)

    def create_directory(self, path: str, root_path: str | None = None) -> dict:
        """创建目录。"""
        return filesystem_service.create_directory(path, root_path=root_path)

    def rename_directory(
        self,
        old_path: str,
        new_name: str,
        root_path: str | None = None,
    ) -> dict:
        """重命名目录。"""
        return filesystem_service.rename_directory(
            old_path,
            new_name,
            root_path=root_path,
        )

    def delete_directory(self, path: str, root_path: str | None = None) -> None:
        """删除目录（递归删除非空目录）。"""
        filesystem_service.delete_directory(path, root_path=root_path)

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
