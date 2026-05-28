import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.plugins.komga.plugin import KomgaPlugin


@pytest.fixture
def plugin():
    return KomgaPlugin()


def test_plugin_metadata(plugin):
    assert plugin.name == "komga"
    assert plugin.display_name == "Komga"
    assert "url" in str(plugin.config_schema)


@pytest.mark.asyncio
@patch("app.plugins.komga.plugin.httpx.AsyncClient")
async def test_test_connection_success(mock_client_cls, plugin):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = await plugin.test_connection({
        "url": "http://localhost:8080",
        "username": "admin",
        "password": "password",
    })
    assert result is True


@pytest.mark.asyncio
@patch("app.plugins.komga.plugin.httpx.AsyncClient")
async def test_get_sources(mock_client_cls, plugin):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"id": "lib1", "name": "Manga"},
    ]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    sources = await plugin.get_sources({
        "url": "http://localhost:8080",
        "username": "admin",
        "password": "password",
    })
    assert len(sources) == 1
    assert sources[0].name == "Manga"
