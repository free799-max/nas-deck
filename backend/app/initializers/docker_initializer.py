"""Docker 相关数据初始化。"""

from sqlalchemy import select

from app.database import async_session
from app.models.docker import DockerMirrorConfig


async def init_default_registry() -> None:
    """初始化默认 Docker Hub 镜像仓库配置。"""
    async with async_session() as session:
        result = await session.execute(select(DockerMirrorConfig))
        if not result.scalars().first():
            default_config = DockerMirrorConfig(
                name="Docker Hub",
                search_api_url="https://registry.hub.docker.com",
                mirror_url=None,
                enable_mirror=False,
                username=None,
                password=None,
                is_default=True,
            )
            session.add(default_config)
            await session.commit()
