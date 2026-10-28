"""镜像标签获取测试（不访问网络）。"""

import pytest

from app.services.docker import image_service


@pytest.fixture(autouse=True)
def clear_tag_cache():
    image_service._tag_cache.clear()
    yield
    image_service._tag_cache.clear()


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("nginx", ("", "library/nginx")),
        ("nginx:1.27", ("", "library/nginx")),
        ("docker.io/library/nginx", ("", "library/nginx")),
        ("bitnami/redis", ("", "bitnami/redis")),
        ("ghcr.io/open-webui/open-webui", ("ghcr.io", "open-webui/open-webui")),
        ("ghcr.io/open-webui/open-webui:main", ("ghcr.io", "open-webui/open-webui")),
        ("https://ghcr.io/open-webui/open-webui", ("ghcr.io", "open-webui/open-webui")),
        ("localhost:5000/team/app", ("localhost:5000", "team/app")),
        ("quay.io/prometheus/node-exporter@sha256:abc", ("quay.io", "prometheus/node-exporter")),
    ],
)
def test_split_image_ref(image, expected):
    assert image_service._split_image_ref(image) == expected


def test_sort_tags_newest_first():
    tags = [
        {"name": "old", "last_updated": "2024-01-01T00:00:00Z"},
        {"name": "unknown", "last_updated": ""},
        {"name": "new", "last_updated": "2026-01-01T00:00:00Z"},
    ]
    assert [t["name"] for t in image_service._sort_tags(tags)] == ["new", "old", "unknown"]


@pytest.mark.asyncio
async def test_get_image_tags_uses_registry_for_ghcr(monkeypatch):
    calls = []

    async def fake_registry(host, repo, limit):
        calls.append((host, repo, limit))
        return [{"name": "latest", "last_updated": "2026-01-01T00:00:00Z", "size": 1, "digest": "sha256:x"}]

    async def fake_hub(repo, limit):
        raise AssertionError("不应调用 Docker Hub 接口")

    monkeypatch.setattr(image_service, "_registry_tags", fake_registry)
    monkeypatch.setattr(image_service, "_hub_tags", fake_hub)

    service = image_service.ImageService.__new__(image_service.ImageService)
    tags = await service.get_image_tags("ghcr.io/open-webui/open-webui")

    assert calls and calls[0][:2] == ("ghcr.io", "open-webui/open-webui")
    assert [t["name"] for t in tags] == ["latest"]
    # 第二次走缓存，不再发请求
    await service.get_image_tags("ghcr.io/open-webui/open-webui")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_get_image_tags_swallows_errors(monkeypatch):
    async def fake_registry(host, repo, limit):
        raise RuntimeError("boom")

    monkeypatch.setattr(image_service, "_registry_tags", fake_registry)
    service = image_service.ImageService.__new__(image_service.ImageService)
    assert await service.get_image_tags("ghcr.io/foo/bar") == []
