"""Docker Compose 编排管理器兼容入口。

原 ComposeManager 已迁移到 app.services.compose。
本模块保留旧的导入路径，避免外部代码和测试一次性大面积改动。
"""

from app.core.docker_manager import docker_manager
from app.services.compose import ComposeService, compose_manager, ComposeDiscoveryService

# 兼容旧测试中的类名
ComposeManager = ComposeService

__all__ = [
    "docker_manager",
    "compose_manager",
    "ComposeService",
    "ComposeManager",
    "ComposeDiscoveryService",
]
