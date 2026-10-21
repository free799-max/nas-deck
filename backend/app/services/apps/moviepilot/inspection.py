"""MoviePilot 配置健康检测与自动修复能力。

下载器/媒体服务器检测项的修复通过 ``ctx['wire']`` 回调重跑所在组的
自动装配（wiring）完成；目录、硬链接、媒体库同步、订阅搜索等检测项
直接写回 MoviePilot 系统设置。

检测项参考 MoviePilot 官方配置指引，覆盖「基础装配 → 站点媒体 →
体验优化」三个层次，并尽量把可以安全写入的设置做成自动修复。
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.services.apps.base import FixResultItem, InspectItem, InspectReport

logger = logging.getLogger(__name__)

# 下载器/媒体服务器检测项与设置项 key 的对应关系
_WIRED_ITEMS = {
    "downloader_configured": ("Downloaders", "downloaders", "下载器"),
    "mediaserver_configured": ("MediaServers", "mediaservers", "媒体服务器"),
}

# 检测项分组（前端按分组渲染）
_GROUP_CORE = "核心配置"
_GROUP_MEDIA = "站点与媒体"
_GROUP_OPTIMIZE = "体验与安全"

# 无法从编排共享配置推导时的容器内默认路径
_DEFAULT_DOWNLOAD_PATH = "/downloads"
_DEFAULT_LIBRARY_PATH = "/media"

# 通知渠道在部分 MoviePilot 版本中的旧键名
_NOTIFICATION_KEYS = ("Notifications", "NotificationChannels")

# 整理方式的中文说明
_TRANSFER_TYPE_LABELS = {
    "link": "硬链接",
    "softlink": "软链接",
    "copy": "复制",
    "move": "移动",
}


class MoviePilotInspectionMixin:
    """MoviePilot 配置健康检测能力。"""

    TIMEOUT = 10.0

    async def inspect(self, ctx: dict) -> InspectReport:
        """检测认证、装配、目录、站点与常用优化项。"""
        base_url = str(ctx.get("url") or "").rstrip("/")
        api_key = ctx.get("api_key") or ""
        if not base_url or not api_key:
            return InspectReport(
                supported=True,
                items=[
                    InspectItem(
                        id="auth",
                        title="API Key 认证",
                        status="error",
                        message="缺少访问地址或 API Key，无法检测",
                        category=_GROUP_CORE,
                    )
                ],
            )

        auth_item = await self._check_auth(base_url, api_key)
        if auth_item.status != "ok":
            # 认证失败时其余检测项没有意义
            return InspectReport(supported=True, items=[auth_item])

        items: list[InspectItem] = [auth_item, *await self._inspect_wired_items(ctx)]
        items.extend(await self._inspect_directories(base_url, api_key))
        items.extend(await self._inspect_mediaserver_libraries(base_url, api_key))
        items.append(await self._inspect_sites(base_url, api_key))

        env_ok, env, env_err = await self._get_env(base_url, api_key)
        if env_ok:
            items.append(self._inspect_site_auth(env))
            items.append(self._inspect_subscribe_search(env))
            items.append(await self._inspect_notifications(base_url, api_key))
            items.append(self._inspect_proxy(env))
            items.append(self._inspect_github_token(env))
            items.append(await self._inspect_plugins(base_url, api_key))
            items.append(self._inspect_api_token(env, api_key))
        else:
            items.append(
                InspectItem(
                    id="settings_readable",
                    title="系统设置读取",
                    status="warn",
                    message=f"无法读取系统设置，部分优化项已跳过: {env_err}",
                    category=_GROUP_OPTIMIZE,
                )
            )
        return InspectReport(supported=True, items=items)

    async def apply_fix(self, ctx: dict, item_ids: list[str]) -> list[FixResultItem]:
        """修复可自动修复的检测项，写入后回读复验。"""
        base_url = str(ctx.get("url") or "").rstrip("/")
        api_key = ctx.get("api_key") or ""
        wire = ctx.get("wire")
        results: list[FixResultItem] = []
        wired = False
        for item_id in item_ids:
            if item_id in _WIRED_ITEMS:
                if wire is None:
                    results.append(
                        FixResultItem(
                            id=item_id,
                            ok=False,
                            message="缺少装配回调，无法自动修复",
                        )
                    )
                    continue
                try:
                    if not wired:
                        # 多个装配类检测项只重跑一次装配
                        await wire()
                        wired = True
                except Exception as exc:
                    logger.exception("重跑自动装配失败")
                    results.append(
                        FixResultItem(id=item_id, ok=False, message=f"重跑装配失败: {exc}")
                    )
                    continue
                ok, message = await self._check_wired_item(
                    ctx, base_url, api_key, item_id
                )
                results.append(
                    FixResultItem(
                        id=item_id,
                        ok=ok,
                        message=(
                            "已重新装配并验证通过"
                            if ok
                            else f"重新装配后仍未通过: {message}"
                        ),
                    )
                )
            elif item_id == "directories_configured":
                ok, message = await self._fix_directories(ctx, base_url, api_key)
                results.append(FixResultItem(id=item_id, ok=ok, message=message))
            elif item_id == "transfer_mode":
                ok, message = await self._fix_transfer_mode(base_url, api_key)
                results.append(FixResultItem(id=item_id, ok=ok, message=message))
            elif item_id == "mediaserver_library_sync":
                ok, message = await self._fix_mediaserver_library_sync(
                    base_url, api_key
                )
                results.append(FixResultItem(id=item_id, ok=ok, message=message))
            elif item_id == "subscribe_search":
                ok, message = await self._fix_subscribe_search(base_url, api_key)
                results.append(FixResultItem(id=item_id, ok=ok, message=message))
            else:
                results.append(
                    FixResultItem(id=item_id, ok=False, message="该检测项不支持自动修复")
                )
        return results

    # ---------------- 基础检测 ----------------

    async def _check_auth(self, base_url: str, api_key: str) -> InspectItem:
        """通过用户接口验证 API Key 是否可用。"""
        ok, _, err = await self._api_get(base_url, api_key, "/api/v1/user/")
        if ok:
            return InspectItem(
                id="auth",
                title="API Key 认证",
                status="ok",
                message="认证成功",
                category=_GROUP_CORE,
            )
        return InspectItem(
            id="auth",
            title="API Key 认证",
            status="error",
            message=err or "API Key 认证失败",
            category=_GROUP_CORE,
        )

    async def _inspect_wired_items(self, ctx: dict) -> list[InspectItem]:
        """检测下载器与媒体服务器是否已按装配结果配置。"""
        base_url = str(ctx.get("url") or "").rstrip("/")
        api_key = ctx.get("api_key") or ""
        return [
            await self._inspect_wired_item(ctx, base_url, api_key, item_id)
            for item_id in _WIRED_ITEMS
        ]

    async def _inspect_wired_item(
        self,
        ctx: dict,
        base_url: str,
        api_key: str,
        item_id: str,
    ) -> InspectItem:
        """检测下载器/媒体服务器是否已按装配结果配置且启用。"""
        _, _, title = _WIRED_ITEMS[item_id]
        ok, message, current_names, expected_names = await self._check_wired_item(
            ctx, base_url, api_key, item_id, detail=True
        )
        if current_names is None:
            return InspectItem(
                id=item_id,
                title=title,
                status="error",
                message=message,
                category=_GROUP_CORE,
            )
        return InspectItem(
            id=item_id,
            title=title,
            status="ok" if ok else "error",
            message=message,
            current_value=", ".join(current_names) or None,
            expected_value=", ".join(expected_names) or None,
            fixable=not ok,
            category=_GROUP_CORE,
        )

    async def _check_wired_item(
        self,
        ctx: dict,
        base_url: str,
        api_key: str,
        item_id: str,
        detail: bool = False,
    ):
        """复验下载器/媒体服务器配置，返回 (是否通过, 说明[, 当前名称, 期望名称])。"""
        setting_key, integration_key, title = _WIRED_ITEMS[item_id]
        ok, value, err = await self.get_setting(base_url, api_key, setting_key)
        if not ok:
            result = (False, f"读取{title}配置失败: {err}", None, None)
            return result if detail else (False, f"读取{title}配置失败: {err}")

        enabled = [
            str(i.get("name"))
            for i in value
            if isinstance(i, dict) and i.get("enabled") and i.get("name")
        ] if isinstance(value, list) else []

        integrations = ctx.get("integrations") or {}
        expected = [
            str(rec.get("name"))
            for rec in integrations.get(integration_key) or []
            if rec.get("status") == "ok" and rec.get("name")
        ]

        if expected:
            missing = [name for name in expected if name not in enabled]
            passed = not missing
            message = (
                f"{title}已按装配结果配置"
                if passed
                else f"装配的{title}未生效: {', '.join(missing)}"
            )
        else:
            passed = bool(enabled)
            message = (
                f"已配置 {len(enabled)} 个启用的{title}"
                if passed
                else f"未配置启用的{title}"
            )
        if detail:
            return passed, message, enabled, expected
        return passed, message

    # ---------------- 目录与整理 ----------------

    async def _inspect_directories(
        self, base_url: str, api_key: str
    ) -> list[InspectItem]:
        """检测下载/媒体库目录与整理方式。"""
        entries, err = await self._get_directories(base_url, api_key)
        if err:
            return [
                InspectItem(
                    id="directories_configured",
                    title="下载与媒体目录",
                    status="error",
                    message=err,
                    category=_GROUP_CORE,
                ),
                self._transfer_item([], unreadable=True),
            ]

        ready = [
            entry
            for entry in entries
            if entry.get("download_path") and entry.get("library_path")
        ]
        if ready:
            names = "、".join(str(e.get("name") or "未命名") for e in ready)
            directory_item = InspectItem(
                id="directories_configured",
                title="下载与媒体目录",
                status="ok",
                message=f"已配置 {len(ready)} 个完整目录",
                current_value=names,
                expected_value="下载目录 + 媒体库目录",
                category=_GROUP_CORE,
            )
        else:
            directory_item = InspectItem(
                id="directories_configured",
                title="下载与媒体目录",
                status="warn",
                message=(
                    "目录配置缺少下载目录或媒体库目录，下载完成后无法自动整理入库"
                    if entries
                    else "未配置下载/媒体库目录，下载完成后无法自动整理入库"
                ),
                expected_value="下载目录 + 媒体库目录",
                fixable=True,
                category=_GROUP_CORE,
            )
        return [directory_item, self._transfer_item(entries)]

    def _transfer_item(
        self, entries: list[dict], unreadable: bool = False
    ) -> InspectItem:
        """根据目录配置判断整理方式是否为硬链接。"""
        local_entries = [
            entry
            for entry in entries
            if str(entry.get("storage") or "local") == "local"
            and entry.get("library_path")
        ]
        if unreadable:
            return InspectItem(
                id="transfer_mode",
                title="硬链接整理",
                status="warn",
                message="无法读取目录配置，暂时无法判断整理方式",
                category=_GROUP_CORE,
            )
        if not local_entries:
            return InspectItem(
                id="transfer_mode",
                title="硬链接整理",
                status="warn",
                message="尚未配置本地整理目录，无法启用硬链接",
                category=_GROUP_CORE,
            )

        modes = {
            str(entry.get("transfer_type") or "").strip() for entry in local_entries
        }
        current = "、".join(
            _TRANSFER_TYPE_LABELS.get(mode, mode or "未设置") for mode in sorted(modes)
        )
        if modes == {"link"}:
            return InspectItem(
                id="transfer_mode",
                title="硬链接整理",
                status="ok",
                message="已启用硬链接整理，重复文件不额外占用空间",
                current_value="硬链接",
                expected_value="硬链接",
                category=_GROUP_CORE,
            )
        return InspectItem(
            id="transfer_mode",
            title="硬链接整理",
            status="warn",
            message="当前整理方式不是硬链接，会额外占用磁盘空间；改为硬链接前请确认下载目录与媒体库在同一磁盘",
            current_value=current,
            expected_value="硬链接",
            fixable=True,
            category=_GROUP_CORE,
        )

    # ---------------- 媒体服务器 ----------------

    async def _inspect_mediaserver_libraries(
        self, base_url: str, api_key: str
    ) -> list[InspectItem]:
        """检测媒体服务器连通性与媒体库同步范围。"""
        ok, value, err = await self.get_setting(base_url, api_key, "MediaServers")
        if not ok:
            return [
                InspectItem(
                    id="mediaserver_connection",
                    title="媒体服务器连接",
                    status="error",
                    message=f"读取媒体服务器配置失败: {err}",
                    category=_GROUP_MEDIA,
                ),
                InspectItem(
                    id="mediaserver_library_sync",
                    title="媒体库同步",
                    status="warn",
                    message="无法读取媒体服务器配置，暂时无法检测同步范围",
                    category=_GROUP_MEDIA,
                ),
            ]

        servers = [
            entry
            for entry in (value if isinstance(value, list) else [])
            if isinstance(entry, dict) and entry.get("enabled") and entry.get("name")
        ]
        if not servers:
            return [
                InspectItem(
                    id="mediaserver_connection",
                    title="媒体服务器连接",
                    status="error",
                    message="未启用媒体服务器，整理完成后无法自动刷新媒体库",
                    category=_GROUP_MEDIA,
                ),
                InspectItem(
                    id="mediaserver_library_sync",
                    title="媒体库同步",
                    status="warn",
                    message="未启用媒体服务器，无法设置媒体库同步",
                    category=_GROUP_MEDIA,
                ),
            ]

        failures: list[str] = []
        sync_missing: list[str] = []
        synced = 0
        for server in servers:
            name = str(server.get("name"))
            libs_ok, libs, libs_err = await self._fetch_libraries(
                base_url, api_key, name
            )
            if not libs_ok:
                failures.append(f"{name}: {libs_err}")
                continue
            if not libs:
                failures.append(f"{name}: 未获取到媒体库")
                continue
            configured = {str(i) for i in (server.get("sync_libraries") or [])}
            missing = [i for i in libs if i not in configured]
            if missing:
                sync_missing.append(f"{name}（缺少 {len(missing)} 个库）")
            else:
                synced += 1

        if failures:
            connection_item = InspectItem(
                id="mediaserver_connection",
                title="媒体服务器连接",
                status="error",
                message="；".join(failures),
                category=_GROUP_MEDIA,
            )
        else:
            connection_item = InspectItem(
                id="mediaserver_connection",
                title="媒体服务器连接",
                status="ok",
                message=f"已连接 {len(servers)} 个媒体服务器",
                current_value="、".join(str(s.get("name")) for s in servers),
                category=_GROUP_MEDIA,
            )

        if sync_missing:
            sync_item = InspectItem(
                id="mediaserver_library_sync",
                title="媒体库同步",
                status="warn",
                message=(
                    "以下媒体服务器未选择同步库，整理完成后不会触发对应媒体库刷新："
                    + "；".join(sync_missing)
                ),
                current_value=f"{synced}/{len(servers)} 已全选",
                expected_value="同步全部媒体库",
                fixable=True,
                category=_GROUP_MEDIA,
            )
        elif failures:
            sync_item = InspectItem(
                id="mediaserver_library_sync",
                title="媒体库同步",
                status="warn",
                message="媒体服务器连接异常，暂时无法检测同步范围",
                category=_GROUP_MEDIA,
            )
        else:
            sync_item = InspectItem(
                id="mediaserver_library_sync",
                title="媒体库同步",
                status="ok",
                message="已选择同步全部媒体库",
                current_value=f"{len(servers)}/{len(servers)} 已全选",
                expected_value="同步全部媒体库",
                category=_GROUP_MEDIA,
            )
        return [connection_item, sync_item]

    async def _fetch_libraries(
        self, base_url: str, api_key: str, server_name: str
    ) -> tuple[bool, list[str], str | None]:
        """读取指定媒体服务器的媒体库 ID 列表。"""
        ok, data, err = await self._api_get(
            base_url,
            api_key,
            f"/api/v1/mediaserver/library?server={quote(server_name)}",
        )
        if not ok:
            return False, [], err
        if not isinstance(data, list):
            return False, [], "媒体库接口返回异常"
        ids = [
            str(lib.get("id"))
            for lib in data
            if isinstance(lib, dict) and lib.get("id") is not None
        ]
        return True, ids, None

    # ---------------- 站点与通知 ----------------

    async def _inspect_sites(self, base_url: str, api_key: str) -> InspectItem:
        """检测站点数量。"""
        ok, data, err = await self._api_get(base_url, api_key, "/api/v1/site/")
        if not ok:
            return InspectItem(
                id="sites_configured",
                title="站点配置",
                status="error",
                message=f"读取站点列表失败: {err}",
                category=_GROUP_MEDIA,
            )
        count = len(data) if isinstance(data, list) else 0
        if count:
            return InspectItem(
                id="sites_configured",
                title="站点配置",
                status="ok",
                message=f"已配置 {count} 个站点",
                current_value=str(count),
                category=_GROUP_MEDIA,
            )
        return InspectItem(
            id="sites_configured",
            title="站点配置",
            status="warn",
            message="尚未添加站点，搜索、订阅和资源下载将无法工作；可在 MoviePilot 站点页添加或通过 CookieCloud 同步",
            expected_value="至少 1 个站点",
            category=_GROUP_MEDIA,
        )

    def _inspect_site_auth(self, env: dict) -> InspectItem:
        """检测用户站点认证配置。"""
        auth_site = str(env.get("AUTH_SITE") or "").strip()
        if auth_site:
            return InspectItem(
                id="site_auth",
                title="用户认证",
                status="ok",
                message="已配置认证站点",
                current_value=auth_site,
                category=_GROUP_MEDIA,
            )
        return InspectItem(
            id="site_auth",
            title="用户认证",
            status="warn",
            message="未配置用户认证，站点数据、做种统计等站点功能不可用；可在 MoviePilot 头像菜单 → 用户认证中配置",
            category=_GROUP_MEDIA,
        )

    async def _inspect_notifications(
        self, base_url: str, api_key: str
    ) -> InspectItem:
        """检测是否配置了启用的通知渠道。"""
        readable = False
        channels: list[dict] = []
        for key in _NOTIFICATION_KEYS:
            ok, value, _ = await self.get_setting(base_url, api_key, key)
            if not ok:
                continue
            readable = True
            if isinstance(value, list):
                channels = [
                    item
                    for item in value
                    if isinstance(item, dict) and item.get("enabled")
                ]
                break
        if not readable:
            return InspectItem(
                id="notifications_configured",
                title="通知渠道",
                status="warn",
                message="无法读取通知配置",
                category=_GROUP_OPTIMIZE,
            )
        if channels:
            return InspectItem(
                id="notifications_configured",
                title="通知渠道",
                status="ok",
                message=f"已启用 {len(channels)} 个通知渠道",
                current_value="、".join(
                    str(c.get("name") or c.get("type") or "未命名")
                    for c in channels
                ),
                category=_GROUP_OPTIMIZE,
            )
        return InspectItem(
            id="notifications_configured",
            title="通知渠道",
            status="warn",
            message="未配置通知渠道，下载、整理和订阅结果无法推送；可在 MoviePilot 设定 → 通知中配置",
            category=_GROUP_OPTIMIZE,
        )

    # ---------------- 体验与安全 ----------------

    def _inspect_subscribe_search(self, env: dict) -> InspectItem:
        """检测订阅自动搜索是否开启。"""
        enabled = self._as_bool(env.get("SUBSCRIBE_SEARCH"))
        if enabled:
            return InspectItem(
                id="subscribe_search",
                title="订阅自动搜索",
                status="ok",
                message="已开启订阅自动搜索",
                current_value="已开启",
                expected_value="已开启",
                category=_GROUP_OPTIMIZE,
            )
        return InspectItem(
            id="subscribe_search",
            title="订阅自动搜索",
            status="warn",
            message="未开启订阅自动搜索，订阅仅依赖 RSS，可能漏掉资源；开启后会按设定间隔主动搜索",
            current_value="未开启",
            expected_value="已开启",
            fixable=True,
            category=_GROUP_OPTIMIZE,
        )

    def _inspect_proxy(self, env: dict) -> InspectItem:
        """检测网络代理配置。"""
        proxy = str(env.get("PROXY_HOST") or "").strip()
        if proxy:
            return InspectItem(
                id="proxy_configured",
                title="网络代理",
                status="ok",
                message="已配置网络代理",
                current_value=proxy,
                category=_GROUP_OPTIMIZE,
            )
        return InspectItem(
            id="proxy_configured",
            title="网络代理",
            status="warn",
            message="未配置网络代理，访问 TMDB/GitHub 可能较慢或失败；若直连正常可忽略",
            category=_GROUP_OPTIMIZE,
        )

    def _inspect_github_token(self, env: dict) -> InspectItem:
        """检测 GitHub Token 配置。"""
        token = str(env.get("GITHUB_TOKEN") or "").strip()
        if token:
            return InspectItem(
                id="github_token",
                title="GitHub Token",
                status="ok",
                message="已配置 GitHub Token",
                category=_GROUP_OPTIMIZE,
            )
        return InspectItem(
            id="github_token",
            title="GitHub Token",
            status="warn",
            message="未配置 GitHub Token，插件安装和自动更新可能触发 API 限流",
            category=_GROUP_OPTIMIZE,
        )

    async def _inspect_plugins(self, base_url: str, api_key: str) -> InspectItem:
        """检测已安装插件数量。"""
        ok, data, err = await self._api_get(
            base_url, api_key, "/api/v1/plugin/installed"
        )
        if not ok:
            return InspectItem(
                id="plugins_installed",
                title="插件安装",
                status="warn",
                message=f"读取已安装插件失败: {err}",
                category=_GROUP_OPTIMIZE,
            )
        count = len(data) if isinstance(data, list) else 0
        if count:
            return InspectItem(
                id="plugins_installed",
                title="插件安装",
                status="ok",
                message=f"已安装 {count} 个插件",
                current_value=str(count),
                category=_GROUP_OPTIMIZE,
            )
        return InspectItem(
            id="plugins_installed",
            title="插件安装",
            status="warn",
            message="未安装插件，可按需安装站点同步、自动签到、目录监控等增强插件",
            category=_GROUP_OPTIMIZE,
        )

    def _inspect_api_token(self, env: dict, fallback: str) -> InspectItem:
        """检测 API Token 强度。"""
        token = str(env.get("API_TOKEN") or fallback or "")
        if len(token) >= 16 and token.lower() != "moviepilot":
            return InspectItem(
                id="api_token_strength",
                title="API Token 强度",
                status="ok",
                message="API Token 长度符合安全要求",
                category=_GROUP_OPTIMIZE,
            )
        return InspectItem(
            id="api_token_strength",
            title="API Token 强度",
            status="warn",
            message="API Token 过短，建议使用 16 位以上复杂字符串，并在修改后同步更新本应用的认证配置",
            category=_GROUP_OPTIMIZE,
        )

    # ---------------- 自动修复 ----------------

    async def _fix_directories(
        self, ctx: dict, base_url: str, api_key: str
    ) -> tuple[bool, str]:
        """补全下载/媒体库目录配置。"""
        entries, err = await self._get_directories(base_url, api_key)
        if err:
            return False, f"读取目录配置失败: {err}"

        download_path = self._shared_container_path(ctx, "download")
        library_path = self._shared_container_path(ctx, "library")
        if not entries:
            entries = [self._default_directory(download_path, library_path)]
        else:
            for entry in entries:
                if not entry.get("download_path"):
                    entry["download_path"] = download_path
                if not entry.get("library_path"):
                    entry["library_path"] = library_path
                entry.setdefault("storage", "local")
                entry.setdefault("library_storage", "local")
                if not entry.get("transfer_type"):
                    entry["transfer_type"] = "link"

        ok, err = await self.set_setting(base_url, api_key, "Directories", entries)
        if not ok:
            return False, err or "写入目录配置失败"

        after, err = await self._get_directories(base_url, api_key)
        if err:
            return False, f"写入后回读验证失败: {err}"
        if any(e.get("download_path") and e.get("library_path") for e in after):
            return True, "已写入下载/媒体库目录配置"
        return False, "写入后回读验证失败"

    async def _fix_transfer_mode(
        self, base_url: str, api_key: str
    ) -> tuple[bool, str]:
        """把本地整理目录的整理方式改为硬链接。"""
        entries, err = await self._get_directories(base_url, api_key)
        if err:
            return False, f"读取目录配置失败: {err}"
        if not entries:
            return False, "尚未配置目录，请先修复目录配置"

        changed = 0
        for entry in entries:
            if (
                str(entry.get("storage") or "local") == "local"
                and entry.get("library_path")
                and entry.get("transfer_type") != "link"
            ):
                entry["transfer_type"] = "link"
                changed += 1
        if changed == 0:
            return True, "整理方式已是硬链接"

        ok, err = await self.set_setting(base_url, api_key, "Directories", entries)
        if not ok:
            return False, err or "写入目录配置失败"
        after, err = await self._get_directories(base_url, api_key)
        if err:
            return False, f"写入后回读验证失败: {err}"
        if all(
            str(e.get("transfer_type") or "") == "link"
            for e in after
            if str(e.get("storage") or "local") == "local" and e.get("library_path")
        ):
            return True, f"已把 {changed} 个目录改为硬链接整理"
        return False, "写入后回读验证失败"

    async def _fix_mediaserver_library_sync(
        self, base_url: str, api_key: str
    ) -> tuple[bool, str]:
        """让已启用的媒体服务器同步全部媒体库。"""
        ok, value, err = await self.get_setting(base_url, api_key, "MediaServers")
        if not ok:
            return False, f"读取媒体服务器配置失败: {err}"
        servers = [
            dict(entry)
            for entry in (value if isinstance(value, list) else [])
            if isinstance(entry, dict) and entry.get("enabled") and entry.get("name")
        ]
        if not servers:
            return False, "未启用媒体服务器，无法设置媒体库同步"

        changed = 0
        failures: list[str] = []
        for server in servers:
            name = str(server.get("name"))
            libs_ok, libs, libs_err = await self._fetch_libraries(
                base_url, api_key, name
            )
            if not libs_ok:
                failures.append(f"{name}: {libs_err}")
                continue
            if not libs:
                failures.append(f"{name}: 未获取到媒体库")
                continue
            if set(libs) - {str(i) for i in (server.get("sync_libraries") or [])}:
                server["sync_libraries"] = libs
                changed += 1

        if changed == 0:
            if failures:
                return False, "；".join(failures)
            return True, "媒体库同步已是最新"

        ok, err = await self.set_setting(
            base_url, api_key, "MediaServers", servers
        )
        if not ok:
            return False, err or "写入媒体服务器配置失败"
        if failures:
            return (
                True,
                f"已更新 {changed} 个媒体服务器；未完成: " + "；".join(failures),
            )
        return True, f"已把 {changed} 个媒体服务器设为同步全部媒体库"

    async def _fix_subscribe_search(
        self, base_url: str, api_key: str
    ) -> tuple[bool, str]:
        """开启订阅自动搜索。"""
        ok, err = await self.set_setting(
            base_url, api_key, "SUBSCRIBE_SEARCH", True
        )
        if not ok:
            return False, err or "写入订阅搜索设置失败"
        ok, value, err = await self.get_setting(
            base_url, api_key, "SUBSCRIBE_SEARCH"
        )
        if not ok:
            return False, f"写入后回读验证失败: {err}"
        if self._as_bool(value):
            return True, "已开启订阅自动搜索"
        return False, "写入后回读验证失败"

    # ---------------- 工具方法 ----------------

    async def _get_env(
        self, base_url: str, api_key: str
    ) -> tuple[bool, dict, str | None]:
        """读取 MoviePilot 全部运行配置。"""
        ok, data, err = await self._api_get(
            base_url, api_key, "/api/v1/system/env"
        )
        if not ok:
            return False, {}, err
        if not isinstance(data, dict):
            return False, {}, "系统环境接口返回异常"
        return True, data, None

    async def _get_directories(
        self, base_url: str, api_key: str
    ) -> tuple[list[dict], str | None]:
        """读取目录配置列表。"""
        ok, value, err = await self.get_setting(base_url, api_key, "Directories")
        if not ok:
            return [], err
        if not isinstance(value, list):
            return [], None
        return [dict(entry) for entry in value if isinstance(entry, dict)], None

    async def _api_get(
        self, base_url: str, api_key: str, path: str
    ) -> tuple[bool, Any, str | None]:
        """调用 MoviePilot API 并做统一响应解析。"""
        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(
                    f"{base_url}{path}", headers={"X-API-KEY": api_key}
                )
        except httpx.RequestError as exc:
            return False, None, f"无法连接到应用: {exc}"
        return self._parse_response(resp)

    @staticmethod
    def _parse_response(resp: httpx.Response) -> tuple[bool, Any, str | None]:
        """解析 MoviePilot 的 ``{"success": ..., "data": ...}`` 响应。"""
        if resp.status_code in (401, 403):
            return False, None, "API Key 认证失败"
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        # 部分接口以 5xx 返回结构化失败原因（如媒体服务器不可达），
        # 优先透传业务 message，便于用户定位
        if isinstance(payload, dict) and payload.get("success") is False:
            return False, None, (
                payload.get("message")
                or f"请求失败: HTTP {resp.status_code}"
            )
        if resp.status_code >= 400:
            return False, None, f"请求失败: HTTP {resp.status_code}"
        if payload is None:
            return False, None, "接口返回异常"
        if isinstance(payload, dict) and "data" in payload:
            return True, payload["data"], None
        return True, payload, None

    @staticmethod
    def _shared_container_path(ctx: dict, kind: str) -> str:
        """从编排共享存储映射中推导下载/媒体库容器路径。"""
        volumes = (ctx.get("shared_config") or {}).get("volumes") or []
        for volume in volumes:
            if not isinstance(volume, dict):
                continue
            path = str(volume.get("container_path") or "").strip()
            if not path:
                continue
            lowered = path.lower()
            if kind == "download" and "download" in lowered:
                return path
            if kind == "library" and "media" in lowered:
                return path
        return _DEFAULT_DOWNLOAD_PATH if kind == "download" else _DEFAULT_LIBRARY_PATH

    @staticmethod
    def _default_directory(download_path: str, library_path: str) -> dict:
        """生成一份适合影视自动化的默认目录配置。"""
        return {
            "name": "默认",
            "priority": 1,
            "storage": "local",
            "download_path": download_path,
            "download_type_folder": True,
            "download_category_folder": True,
            "monitor_type": "downloader",
            "monitor_mode": "fast",
            "transfer_type": "link",
            "overwrite_mode": "size",
            "library_path": library_path,
            "library_storage": "local",
            "library_type_folder": True,
            "library_category_folder": True,
            "renaming": True,
            "scraping": True,
            "notify": True,
        }

    @staticmethod
    def _as_bool(value: Any) -> bool:
        """兼容布尔值、字符串和数字形式的开关读取。"""
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
