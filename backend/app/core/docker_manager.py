"""
Docker 客户端管理器模块。

提供对 Docker 守护进程的封装，支持以下功能：
- 查询容器列表（支持过滤条件）
- 获取单个容器详情
- 对容器执行启动、停止、重启操作
- 获取容器日志
- 检测 Docker 服务是否可用及容器健康状态

本模块在导入时会创建一个全局单例 docker_manager，供其他模块直接使用。
"""

import os
import shutil

import docker


class DockerManager:
    """Docker 容器管理器，封装 Docker SDK 的常用操作。

    通过 docker.from_env() 初始化客户端连接，所有方法内部均处理了
    Docker 不可用的情况，确保在 Docker 未安装或未启动时不会抛出异常。

    Attributes:
        _ALLOWED_ACTIONS: 允许执行的容器操作白名单，防止执行任意方法。
        _client: Docker SDK 客户端实例，连接失败时为 None。
    """

    # 允许对容器执行的操作白名单，仅限 start / stop / restart
    _ALLOWED_ACTIONS = frozenset({"start", "stop", "restart"})

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

    def container_action(self, container_id: str, action: str):
        """对指定容器执行操作（启动、停止、重启）。

        Args:
            container_id: 目标容器的 ID。
            action: 要执行的操作名称，必须是 "start"、"stop" 或 "restart" 之一。

        Raises:
            ValueError: 当 action 不在允许的操作白名单中时抛出。
            RuntimeError: 当 Docker 服务不可用时抛出。
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
        """获取本地镜像列表。

        Returns:
            list[dict]: 格式化后的镜像信息列表，包含 id、tags、size、created、containers。
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
            result.append({
                "id": img.id.split(":")[-1][:12] if ":" in img.id else img.id[:12],
                "tags": attrs.get("RepoTags") or ["<none>:<none>"],
                "size": attrs.get("Size", 0),
                "created": attrs.get("Created", ""),
                "containers": image_usage.get(img.id, 0),
            })
        return result

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
        api_url: str | None = None,
        mirror_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> list[dict]:
        """搜索镜像。

        当提供 api_url 时，调用自定义镜像搜索 API；否则通过 Docker Hub v2 API 搜索。
        支持 Basic Auth 认证，主地址失败时可 fallback 到镜像地址。

        第三方 API 调用格式: {api_url}?search={query}
        Docker Hub 格式: {api_url}?q={query}&page_size=20

        Args:
            query: 搜索关键词。
            api_url: 自定义镜像搜索 API 主地址，为 None 时使用 Docker Hub。
            mirror_url: 镜像搜索 API 镜像地址，主地址失败时作为 fallback。
            username: 认证用户名。
            password: 认证密码。

        Returns:
            list[dict]: 搜索结果列表，包含 name、description、star_count、official。
        """
        import httpx
        import urllib.parse

        if not query.strip():
            return []

        auth = (username, password) if username and password else None

        def _do_search(url: str, is_docker_hub: bool = False) -> list[dict] | None:
            """执行单次搜索请求，返回结果或 None（表示失败）。"""
            try:
                resp = httpx.get(url, timeout=10, auth=auth)
                resp.raise_for_status()
                data = resp.json()
                if is_docker_hub:
                    results = data.get("results", [])
                    return [
                        {
                            "name": r.get("repo_name", ""),
                            "description": r.get("short_description", ""),
                            "star_count": r.get("star_count", 0),
                            "official": r.get("is_official", False),
                        }
                        for r in results
                    ]
                # 适配两种常见返回格式: 直接列表 或 嵌套在 results 中
                results = data if isinstance(data, list) else data.get("results", [])
                return [
                    {
                        "name": r.get("name", ""),
                        "description": r.get("description", ""),
                        "star_count": r.get("star_count", 0),
                        "official": r.get("official", False),
                    }
                    for r in results
                ]
            except Exception:
                return None

        def _is_docker_hub_format(url: str) -> bool:
            """判断 URL 是否为 Docker Hub v2 搜索 API 格式。"""
            return url.rstrip("/").endswith("/v2/search/repositories") or "hub.docker.com" in url

        if api_url:
            # 优先使用主地址（Docker Hub 官方 API 格式）
            if _is_docker_hub_format(api_url):
                url = api_url.rstrip("/") + "?q=" + urllib.parse.quote(query.strip()) + "&page_size=20"
                results = _do_search(url, is_docker_hub=True)
            else:
                # 第三方 API 格式
                url = api_url.rstrip("/") + "?search=" + urllib.parse.quote(query.strip())
                results = _do_search(url)
            if results is not None:
                return results
            # 主地址失败，尝试镜像地址
            if mirror_url:
                if _is_docker_hub_format(mirror_url):
                    url = mirror_url.rstrip("/") + "?q=" + urllib.parse.quote(query.strip()) + "&page_size=20"
                    results = _do_search(url, is_docker_hub=True)
                else:
                    url = mirror_url.rstrip("/") + "?search=" + urllib.parse.quote(query.strip())
                    results = _do_search(url)
                if results is not None:
                    return results
            return []

        # 默认使用 Docker Hub v2 API
        url = (
            "https://hub.docker.com/v2/search/repositories?q="
            + urllib.parse.quote(query)
            + "&page_size=20"
        )
        results = _do_search(url, is_docker_hub=True)
        return results if results is not None else []

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

    def _format_container(self, container) -> dict:
        """将 Docker 容器对象格式化为字典。

        提取容器的基本信息和健康检查状态。

        Args:
            container: Docker SDK 的 Container 对象。

        Returns:
            dict: 包含 id（短 ID）、name、status、health、image 的字典。
        """
        # 默认健康状态为 unknown
        health = "unknown"
        # 从容器属性中提取健康检查状态
        state = container.attrs.get("State", {})
        if "Health" in state:
            health = state["Health"].get("Status", "unknown")
        return {
            "id": container.id[:12],  # 使用 12 位短 ID，与 docker 命令行一致
            "name": container.name,
            "status": container.status,
            "health": health,
            "image": str(container.image.tags[0]) if container.image.tags else "unknown",
        }


# 全局单例，供其他模块直接导入使用
docker_manager = DockerManager()
