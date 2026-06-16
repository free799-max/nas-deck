import pytest

from app.plugins.base import BasePlugin, Source, Item
from app.core.plugin_loader import PluginLoader


class FakePlugin(BasePlugin):
    name = "fake"
    display_name = "Fake Plugin"
    version = "1.0.0"
    description = "A fake plugin for testing"
    config_schema = {"type": "object", "properties": {"url": {"type": "string"}}}

    async def test_connection(self, config: dict) -> bool:
        return config.get("url") == "http://valid"

    async def get_sources(self, config: dict) -> list[Source]:
        return [Source(id="lib-1", name="Library 1")]

    async def get_items(self, config: dict, source_id: str) -> list[Item]:
        return [Item(id="item-1", title="Test Item", source_id=source_id, meta={})]



def test_base_plugin_interface():
    plugin = FakePlugin()
    assert plugin.name == "fake"
    assert plugin.config_schema is not None


@pytest.mark.asyncio
async def test_plugin_test_connection():
    plugin = FakePlugin()
    assert await plugin.test_connection({"url": "http://valid"}) is True
    assert await plugin.test_connection({"url": "http://invalid"}) is False


@pytest.mark.asyncio
async def test_plugin_get_sources():
    plugin = FakePlugin()
    sources = await plugin.get_sources({})
    assert len(sources) == 1
    assert sources[0].name == "Library 1"


@pytest.mark.asyncio
async def test_plugin_get_items():
    plugin = FakePlugin()
    items = await plugin.get_items({}, "lib-1")
    assert len(items) == 1
    assert items[0].title == "Test Item"
    assert items[0].source_id == "lib-1"



def test_plugin_loader_register():
    loader = PluginLoader()
    loader.register(FakePlugin)
    assert "fake" in loader.plugins
    assert loader.get("fake") is not None


def test_plugin_loader_get_nonexistent():
    loader = PluginLoader()
    assert loader.get("nonexistent") is None


def test_plugin_loader_list():
    loader = PluginLoader()
    loader.register(FakePlugin)
    plugins = loader.list_plugins()
    assert len(plugins) == 1
    assert plugins[0]["name"] == "fake"
    assert plugins[0]["display_name"] == "Fake Plugin"
    assert plugins[0]["version"] == "1.0.0"
    assert "config_schema" in plugins[0]


def test_plugin_loader_list_empty():
    loader = PluginLoader()
    assert loader.list_plugins() == []
