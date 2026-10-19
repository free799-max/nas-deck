"""业务服务层。

业务逻辑统一放在 services/，core/ 只保留基础设施。

按功能域进一步拆分为：
- services/docker/ — Docker 容器/镜像/宿主机/拉取任务/客户端管理器
- services/compose/ — Docker Compose 编排与自动发现
"""

from app.services.compose import (
    ComposeDiscoveryService,
    ComposeService,
    compose_manager,
)
from app.services.docker import (
    ContainerService,
    DockerManager,
    HostService,
    ImagePullTaskManager,
    ImageService,
    docker_manager,
    task_manager,
)

__all__ = [
    "ComposeDiscoveryService",
    "ComposeService",
    "compose_manager",
    "ContainerService",
    "DockerManager",
    "ImageService",
    "HostService",
    "ImagePullTaskManager",
    "docker_manager",
    "task_manager",
]
