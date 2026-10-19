"""数据库连接与会话管理模块。

基于 SQLAlchemy 2.0 异步引擎，提供：
- 异步引擎和会话工厂
- ORM 声明式基类
- 依赖注入用的数据库会话生成器

表结构与内置数据由 alembic 迁移负责（见 main.py lifespan）。
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# 异步数据库引擎
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# 异步会话工厂，expire_on_commit=False 避免提交后属性过期
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """ORM 声明式基类，所有模型类继承此类。"""
    pass


async def get_db():
    """数据库会话生成器，用作 FastAPI 依赖注入。

    自动管理事务：正常完成时 commit，异常时 rollback。
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
