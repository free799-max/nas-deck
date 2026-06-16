"""Docker 客户端管理器兼容入口。

原 DockerManager / ImagePullTaskManager 已迁移到 app.services/。
本模块保留旧的导入路径，避免外部代码和测试一次性大面积改动。
"""

from app.services.container_service import ContainerService
from app.services.host_service import HostService
from app.services.image_service import ImageService
from app.services.pull_task_service import ImagePullTaskManager, task_manager


class DockerManager(ContainerService, ImageService, HostService):
    """Docker 管理器，继承容器、镜像、宿主机三个服务的能力。"""

    pass


docker_manager = DockerManager()
