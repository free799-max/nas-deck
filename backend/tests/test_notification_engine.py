import pytest

from app.core.notifiers.base import BaseNotifier
from app.core.notification_engine import NotificationEngine


class FakeNotifier(BaseNotifier):
    name = "fake"
    config_schema = {}

    def __init__(self):
        self.sent = []

    async def send(self, title: str, content: str, config: dict, **kwargs) -> bool:
        self.sent.append({"title": title, "content": content})
        return True

    async def test(self, config: dict) -> bool:
        return config.get("valid", False)


@pytest.mark.asyncio
async def test_notifier_send():
    notifier = FakeNotifier()
    result = await notifier.send("Test", "Content", config={})
    assert result is True
    assert len(notifier.sent) == 1


@pytest.mark.asyncio
async def test_notifier_test_connection():
    notifier = FakeNotifier()
    assert await notifier.test({"valid": True}) is True
    assert await notifier.test({"valid": False}) is False


def test_engine_register_and_list():
    engine = NotificationEngine()
    engine.register(FakeNotifier)
    notifiers = engine.list_notifiers()
    assert len(notifiers) == 1
    assert notifiers[0]["name"] == "fake"


@pytest.mark.asyncio
async def test_engine_send():
    engine = NotificationEngine()
    engine.register(FakeNotifier)
    result = await engine.send("fake", "Title", "Body", config={})
    assert result is True
