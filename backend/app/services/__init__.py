"""业务服务层。

将原本集中在 core/docker_manager.py、core/compose_manager.py 中的业务逻辑
下沉到 services/，让 core/ 只保留基础设施。
"""

from app.services.compose_discovery import ComposeDiscoveryService
from app.services.compose_service import ComposeService, compose_manager
from app.services.container_service import ContainerService
from app.services.host_service import HostService
from app.services.image_service import ImageService
from app.services.pull_task_service import ImagePullTaskManager, task_manager

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
