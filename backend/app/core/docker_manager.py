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
