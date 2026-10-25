"""离线资源容器拷贝测试（mock docker CLI）。"""

import json
import pathlib

import pytest

from app.services.apps import asset_copy
from app.services.apps.offline_assets import MOVIEPILOT
from app.services.apps.asset_copy import (
    AssetCopyError,
    copy_assets,
    find_container,
    marker_matches,
    read_marker,
)

CONTAINER = "abc123"


@pytest.mark.asyncio
async def test_marker_parse(monkeypatch):
    payload = {"image": MOVIEPILOT.assets_image, "revision": "1"}

    async def fake_exec(*args, timeout=300):
        pathlib.Path(args[2]).write_text(json.dumps(payload), encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(asset_copy, "_docker_exec", fake_exec)
    assert await read_marker(CONTAINER, MOVIEPILOT.marker) == payload


def test_marker_matches_requires_image_and_revision():
    assert marker_matches(
        {"image": MOVIEPILOT.assets_image, "revision": "1"}, MOVIEPILOT
    )
    assert not marker_matches({"image": "old:1", "revision": "1"}, MOVIEPILOT)
    assert not marker_matches({"image": MOVIEPILOT.assets_image}, MOVIEPILOT)
    assert not marker_matches(None, MOVIEPILOT)


@pytest.mark.asyncio
async def test_copy_skips_when_marker_matches(monkeypatch):
    calls: list[tuple] = []

    async def fake_exec(*args, timeout=300):
        calls.append(args)
        if args[0] == "cp":
            pathlib.Path(args[2]).write_text(
                json.dumps(
                    {"image": MOVIEPILOT.assets_image, "revision": MOVIEPILOT.revision}
                ),
                encoding="utf-8",
            )
        return 0, "", ""

    monkeypatch.setattr(asset_copy, "_docker_exec", fake_exec)
    result = await copy_assets(CONTAINER, MOVIEPILOT)
    assert result["copied"] is False
    assert len(calls) == 1 and calls[0][0] == "cp"


@pytest.mark.asyncio
async def test_copy_stops_copies_and_restarts(monkeypatch, tmp_path):
    calls: list[tuple] = []
    for name in ("pysite", "cloakbrowser"):
        (tmp_path / name).mkdir()

    async def fake_exec(*args, timeout=300):
        calls.append(args)
        if args[0] == "cp" and args[2] == "-":
            return 1, "", "missing"
        if args[0] == "inspect":
            return 0, "true", ""
        return 0, "", ""

    async def fake_cache(profile, progress=None):
        return tmp_path

    monkeypatch.setattr(asset_copy, "_docker_exec", fake_exec)
    monkeypatch.setattr(asset_copy, "_ensure_cache", fake_cache)
    result = await copy_assets(CONTAINER, MOVIEPILOT, force=True)

    assert result["copied"] is True
    assert result["restarted"] is True
    assert ("stop", CONTAINER) in calls
    for copy in MOVIEPILOT.copies:
        assert (
            "cp",
            f"{tmp_path / asset_copy._source_rel(copy.source)}/.",
            f"{CONTAINER}:{copy.target}",
        ) in calls
    assert ("start", CONTAINER) in calls


@pytest.mark.asyncio
async def test_copy_restarts_container_even_on_failure(monkeypatch, tmp_path):
    calls: list[tuple] = []
    (tmp_path / "pysite").mkdir()
    (tmp_path / "cloakbrowser").mkdir()

    async def fake_exec(*args, timeout=300):
        calls.append(args)
        if args[0] == "cp" and args[2] == "-":
            return 1, "", "missing"
        if args[0] == "inspect":
            return 0, "true", ""
        if args[0] == "cp":
            return 1, "", "copy failed"
        return 0, "", ""

    async def fake_cache(profile, progress=None):
        return tmp_path

    monkeypatch.setattr(asset_copy, "_docker_exec", fake_exec)
    monkeypatch.setattr(asset_copy, "_ensure_cache", fake_cache)
    with pytest.raises(AssetCopyError, match="拷贝插件依赖失败"):
        await copy_assets(CONTAINER, MOVIEPILOT, force=True)

    assert ("start", CONTAINER) in calls


@pytest.mark.asyncio
async def test_find_container_uses_compose_labels(monkeypatch):
    calls: list[tuple] = []

    async def fake_exec(*args, timeout=300):
        calls.append(args)
        return 0, "cid1\ncid2", ""

    monkeypatch.setattr(asset_copy, "_docker_exec", fake_exec)
    assert await find_container("demo", "moviepilot") == "cid1"
    assert calls[0][:2] == ("ps", "-aq")
    assert "label=com.docker.compose.project=demo" in calls[0]
    assert "label=com.docker.compose.service=moviepilot" in calls[0]


@pytest.mark.asyncio
async def test_ensure_cache_extracts_image_once(monkeypatch, tmp_path):
    monkeypatch.setattr(asset_copy, "_cache_root", lambda: tmp_path)
    calls: list[tuple] = []

    async def fake_exec(*args, timeout=300):
        calls.append(args)
        if args[0] == "image":
            return 0, "[]", ""
        if args[0] == "create":
            return 0, "assets1", ""
        if args[0] == "cp":
            (tmp_path / "free5104_moviepilot-assets_2.15.6" / "pysite").mkdir(
                parents=True, exist_ok=True
            )
        return 0, "", ""

    monkeypatch.setattr(asset_copy, "_docker_exec", fake_exec)
    cache = await asset_copy._ensure_cache(MOVIEPILOT, None)
    assert (cache / "pysite").is_dir()
    assert (cache / ".ready").read_text().strip() == MOVIEPILOT.assets_image

    creates = [c for c in calls if c[0] == "create"]
    assert len(creates) == 1

    # 第二次直接命中缓存，不再创建资源容器
    await asset_copy._ensure_cache(MOVIEPILOT, None)
    assert len([c for c in calls if c[0] == "create"]) == 1
