import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.scheduler import SubscriptionChecker


@pytest.mark.asyncio
async def test_check_updates_calls_plugin():
    mock_plugin = MagicMock()
    mock_plugin.check_updates = AsyncMock(return_value=[])

    checker = SubscriptionChecker()
    updates = await checker.check_plugin_updates(
        plugin=mock_plugin,
        config={"url": "http://test"},
        subscriptions=[],
    )
    mock_plugin.check_updates.assert_called_once()
    assert updates == []
