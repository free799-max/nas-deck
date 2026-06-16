"""业务服务层。

将原本集中在 core/docker_manager.py、core/compose_manager.py 中的业务逻辑
下沉到 services/，让 core/ 只保留基础设施。

按功能域进一步拆分为：
- services/docker/ — Docker 容器/镜像/宿主机/拉取任务
- services/compose/ — Docker Compose 编排与自动发现
"""

from app.services.compose import (
    ComposeDiscoveryService,
    ComposeService,
    compose_manager,
)
from app.services.docker import (
    ContainerService,
    HostService,
    ImagePullTaskManager,
    ImageService,
    task_manager,
)

__all__ = [
    "ComposeDiscoveryService",
    "ComposeService",
    "compose_manager",
    "ContainerService",
    "ImageService",
    "HostService",
    "ImagePullTaskManager",
    "task_manager",
]
