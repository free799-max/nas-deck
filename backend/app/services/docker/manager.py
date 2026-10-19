"""Docker 客户端管理器。

组合容器、镜像、宿主机三个服务的能力，提供统一的 Docker 管理入口。
"""

from app.services.docker.container_service import ContainerService
from app.services.docker.host_service import HostService
from app.services.docker.image_service import ImageService


class DockerManager(ContainerService, ImageService, HostService):
    """Docker 管理器，继承容器、镜像、宿主机三个服务的能力。"""

    pass


# 全局单例，供其他模块直接导入使用
docker_manager = DockerManager()
