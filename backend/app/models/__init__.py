"""
模型包初始化模块。

集中导出所有 SQLAlchemy ORM 模型类，方便其他模块通过
`from app.models import User, PluginInstance` 的方式直接引用，
而无需关心模型定义在哪个子模块中。

导出的模型：
- User: 用户模型
- PluginInstance: 插件实例模型
- DockerMirrorConfig: Docker 镜像查询配置模型
- DockerComposeProject: Docker Compose 项目模型
- DockerComposeVersion: Docker Compose 版本模型
- DockerComposeStack: Docker Compose Stack 运行时状态模型
"""

from app.models.user import User
from app.models.plugin import PluginInstance
from app.models.app_store import App
from app.models.orchestration import AppOrchestration, AppInstance, AppInstanceBackup
from app.models.docker import (
    DockerMirrorConfig,
    DockerComposeProject,
    DockerComposeVersion,
    DockerComposeStack,
    COMPOSE_PROJECT_LABEL,
)

# __all__ 显式声明公开导出的模型名称，便于 `from app.models import *` 使用
__all__ = [
    "User", "PluginInstance", "App", "AppOrchestration", "AppInstance", "AppInstanceBackup",
    "DockerMirrorConfig",
    "DockerComposeProject", "DockerComposeVersion", "DockerComposeStack",
    "COMPOSE_PROJECT_LABEL",
]
