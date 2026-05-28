import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.plugin import PluginInstance
from app.models.subscription import Subscription, UpdateLog
from app.models.notification import NotificationChannel
from app.models.docker import DockerContainer


@pytest.mark.asyncio
async def test_user_model_fields():
    """测试 User 模型字段定义"""
    assert hasattr(User, "id")
    assert hasattr(User, "username")
    assert hasattr(User, "hashed_password")
    assert hasattr(User, "role")
    assert hasattr(User, "created_at")


@pytest.mark.asyncio
async def test_plugin_instance_model_fields():
    """测试 PluginInstance 模型字段定义"""
    assert hasattr(PluginInstance, "id")
    assert hasattr(PluginInstance, "plugin_name")
    assert hasattr(PluginInstance, "display_name")
    assert hasattr(PluginInstance, "config")
    assert hasattr(PluginInstance, "enabled")


@pytest.mark.asyncio
async def test_subscription_model_fields():
    """测试 Subscription 模型字段定义"""
    assert hasattr(Subscription, "user_id")
    assert hasattr(Subscription, "instance_id")
    assert hasattr(Subscription, "item_id")
    assert hasattr(Subscription, "item_title")
    assert hasattr(Subscription, "item_meta")
    assert hasattr(Subscription, "status")


@pytest.mark.asyncio
async def test_update_log_model_fields():
    """测试 UpdateLog 模型字段定义"""
    assert hasattr(UpdateLog, "subscription_id")
    assert hasattr(UpdateLog, "title")
    assert hasattr(UpdateLog, "content")
    assert hasattr(UpdateLog, "notified")


@pytest.mark.asyncio
async def test_notification_channel_model_fields():
    """测试 NotificationChannel 模型字段定义"""
    assert hasattr(NotificationChannel, "user_id")
    assert hasattr(NotificationChannel, "type")
    assert hasattr(NotificationChannel, "config")
    assert hasattr(NotificationChannel, "enabled")


@pytest.mark.asyncio
async def test_docker_container_model_fields():
    """测试 DockerContainer 模型字段定义"""
    assert hasattr(DockerContainer, "instance_id")
    assert hasattr(DockerContainer, "container_id")
    assert hasattr(DockerContainer, "name")
    assert hasattr(DockerContainer, "status")
    assert hasattr(DockerContainer, "health")


@pytest.mark.asyncio
async def test_create_and_query_user(client):
    """通过 client fixture 使用测试数据库，创建和查询用户"""
    from app.database import get_db
    from app.main import app

    # 获取 overridden 的 db session
    override_fn = app.dependency_overrides.get(get_db)
    if override_fn:
        async for session in override_fn():
            user = User(username="testuser", hashed_password="hashed", role="admin")
            session.add(user)
            await session.flush()

            result = await session.execute(select(User).where(User.username == "testuser"))
            found = result.scalar_one_or_none()
            assert found is not None
            assert found.username == "testuser"
            assert found.role == "admin"
            break


@pytest.mark.asyncio
async def test_create_plugin_instance_and_subscription(client):
    """测试 PluginInstance 和 Subscription 的创建及关联"""
    from app.database import get_db
    from app.main import app

    override_fn = app.dependency_overrides.get(get_db)
    if override_fn:
        async for session in override_fn():
            user = User(username="admin2", hashed_password="hashed", role="admin")
            instance = PluginInstance(
                plugin_name="jellyfin",
                display_name="My Jellyfin",
                config={"url": "http://localhost:8096"},
                enabled=True,
            )
            session.add_all([user, instance])
            await session.flush()

            sub = Subscription(
                user_id=user.id,
                instance_id=instance.id,
                item_id="movie-123",
                item_title="Test Movie",
                item_meta={"year": 2026},
                status="active",
            )
            session.add(sub)
            await session.flush()

            log = UpdateLog(
                subscription_id=sub.id,
                title="New episode",
                content="Episode 5",
                notified=False,
            )
            session.add(log)
            await session.flush()

            result = await session.execute(select(UpdateLog).where(UpdateLog.subscription_id == sub.id))
            logs = result.scalars().all()
            assert len(logs) == 1
            assert logs[0].title == "New episode"
            break
