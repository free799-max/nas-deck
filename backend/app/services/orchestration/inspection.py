"""编排应用配置健康检测（inspection）与插件管理调度能力。"""

import asyncio
import functools
import logging
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
from app.services.app_store.app_service import _slugify
from app.services.apps import FixResultItem, InspectReport

logger = logging.getLogger(__name__)


class InspectionMixin:
    """编排实例组内应用的检测/修复/插件管理调度能力。"""

    async def inspect_app(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
    ) -> InspectReport:
        """对组内指定应用执行配置健康检测。"""
        group = await self.get_group(db, group_id)
        entry = (group.app_configs or {}).get(app_name)
        if entry is None:
            raise APIException("应用不在该实例组中", 404)
        client = self._resolve_app_client(app_name)
        if client is None:
            return InspectReport(supported=False, items=[])
        ctx = await self._build_inspect_ctx(db, group, app_name, entry)
        return await client.inspect(ctx)

    async def apply_fixes(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
        item_ids: list[str],
    ) -> list[FixResultItem]:
        """对组内指定应用的检测项执行自动修复。"""
        group = await self.get_group(db, group_id)
        entry = (group.app_configs or {}).get(app_name)
        if entry is None:
            raise APIException("应用不在该实例组中", 404)
        client = self._resolve_app_client(app_name)
        if client is None:
            return [
                FixResultItem(id=item_id, ok=False, message="该应用不支持自动修复")
                for item_id in item_ids
            ]
        ctx = await self._build_inspect_ctx(db, group, app_name, entry)
        return await client.apply_fix(ctx, item_ids)

    async def list_app_plugins(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
    ) -> dict:
        """查询应用已安装插件与插件市场列表（当前仅 MoviePilot 支持）。"""
        client, entry = await self._resolve_plugin_context(db, group_id, app_name)
        ok, data, err = await client.list_plugins(
            entry["url"].rstrip("/"), entry.get("api_key") or ""
        )
        if not ok:
            raise APIException(err or "查询插件列表失败", 400)
        return data

    async def install_app_plugin(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
        plugin_id: str,
        repo_url: str | None = None,
    ) -> None:
        """安装应用插件（当前仅 MoviePilot 支持），失败抛 APIException。"""
        client, entry = await self._resolve_plugin_context(db, group_id, app_name)
        ok, err = await client.install_plugin(
            entry["url"].rstrip("/"),
            entry.get("api_key") or "",
            plugin_id,
            repo_url=repo_url,
        )
        if not ok:
            raise APIException(err or "安装插件失败", 400)

    async def _resolve_plugin_context(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
    ):
        """解析插件管理所需的客户端与凭据，不满足条件时抛 APIException。"""
        group = await self.get_group(db, group_id)
        entry = (group.app_configs or {}).get(app_name)
        if entry is None:
            raise APIException("应用不在该实例组中", 404)
        client = self._resolve_app_client(app_name)
        if client is None or not hasattr(client, "list_plugins"):
            raise APIException("该应用不支持插件管理", 400)
        if not entry.get("url") or not entry.get("api_key"):
            raise APIException("该应用缺少访问地址或 API Key", 400)
        return client, entry

    async def _build_inspect_ctx(
        self,
        db: AsyncSession,
        group,
        app_name: str,
        entry: dict,
    ) -> dict:
        """构建应用客户端 inspect/apply_fix 的检测上下文。"""
        container_name = _slugify(f"{group.instance_name}-{app_name}")
        ctx: dict = {
            "url": entry.get("url"),
            "username": entry.get("username"),
            "password": entry.get("password"),
            "api_key": entry.get("api_key"),
            "container_name": container_name,
            "shared_config": group.shared_config or {},
            "integrations": entry.get("integrations"),
            "wire": functools.partial(self._wire_group, group.id),
            # 认证修复后回写 app_configs（如刷新失效的 API Key/重置密码）
            "save_app_config": functools.partial(
                self._save_app_config, db, group.id, app_name
            ),
        }

        # 按宿主端口反查容器内端口：qb 的 Host 头伪装与监听端口期望值
        url = entry.get("url")
        host_port = urlparse(url).port if url else None
        if host_port:
            try:
                container_port = await asyncio.to_thread(
                    self._get_container_port, container_name, host_port
                )
            except Exception:
                logger.warning("获取 %s 容器端口失败", container_name, exc_info=True)
                container_port = None
            if container_port:
                ctx["host_header_port"] = container_port
                ctx["expected_listen_port"] = container_port

        # 媒体服务器应用：注入 MoviePilot 侧的装配记录（webhook 反配检测用）
        for other in (group.app_configs or {}).values():
            records = ((other or {}).get("integrations") or {}).get("mediaservers") or []
            for record in records:
                if record.get("name") == app_name:
                    ctx["mediaserver_wiring"] = record
        return ctx

    async def _save_app_config(
        self,
        db: AsyncSession,
        group_id: int,
        app_name: str,
        fields: dict,
    ) -> None:
        """把认证修复结果合并写入 group.app_configs[app_name] 并提交。"""
        group = await self.get_group(db, group_id)
        app_configs = dict(group.app_configs or {})
        entry = dict(app_configs.get(app_name) or {})
        entry.update({key: value for key, value in fields.items() if value is not None})
        entry.pop("provision_error", None)
        app_configs[app_name] = entry
        group.app_configs = app_configs
        await db.commit()
