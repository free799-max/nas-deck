import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.plugins.moviepilot.plugin import MoviePilotPlugin


@pytest.fixture
def plugin():
    return MoviePilotPlugin()


def test_plugin_metadata(plugin):
    assert plugin.name == "moviepilot"
    assert plugin.display_name == "MoviePilot"
    assert "url" in str(plugin.config_schema)


@pytest.mark.asyncio
@patch("app.plugins.moviepilot.plugin.httpx.AsyncClient")
async def test_test_connection_success(mock_client_cls, plugin):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = await plugin.test_connection({
        "url": "http://localhost:3000",
        "api_key": "test-key",
    })
    assert result is True


@pytest.mark.asyncio
async def test_get_sources_returns_static(plugin):
    sources = await plugin.get_sources({"url": "http://localhost:3000", "api_key": "test"})
    assert len(sources) == 2
    assert sources[0].id == "subscribes"
    assert sources[1].id == "downloading"
