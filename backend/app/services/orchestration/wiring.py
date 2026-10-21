"""编排应用间自动装配（wiring）能力。

部署与账号自动配置完成后，按编排模板 ``app_composition`` 条目中声明的
``integrations``（如 moviepilot 声明 ``{"type": "downloader", "from": "qbittorrent"}``），
把来源应用（下载器/媒体服务器）的访问配置自动写入目标应用（如 MoviePilot）。
装配结果落库到 ``group.app_configs[目标应用]['integrations']``，失败只记录
不影响部署结果。
"""

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.core.background import create_background_task
from app.database import async_session
from app.services.app_store.app_service import _slugify
from app.services.apps import get_client

logger = logging.getLogger(__name__)


class WiringMixin:
    """把编排内来源应用自动装配进目标应用的能力。"""

    def schedule_wiring(self, group_id: int) -> None:
        """后台重跑自动装配（手动触发入口，立即返回）。"""
        create_background_task(self._wire_group(group_id))

    async def _wire_group(self, group_id: int) -> None:
        """按模板 integrations 声明执行装配并落库，异常只记日志。"""
        try:
            await self._do_wire_group(group_id)
        except Exception:
            logger.exception("实例组 %s 自动装配失败", group_id)

    async def _do_wire_group(self, group_id: int) -> None:
        """自动装配主流程。"""
        async with async_session() as db:
            group = await self.get_group(db, group_id)
            instance_name = group.instance_name
            composition = (
                group.orchestration.app_composition if group.orchestration else None
            ) or []
            app_configs = dict(group.app_configs or {})

        # 每个声明了 integrations 的目标应用一份装配结果
        target_results: dict[str, dict] = {}
        for item in composition:
            integrations = item.get("integrations")
            if not integrations:
                continue
            target_name = item.get("app_name")
            if not target_name:
                continue
            target_cfg = app_configs.get(target_name) or {}
            target_error = self._check_target(target_cfg)
            results = target_results.setdefault(
                target_name,
                {
                    "wired_at": datetime.now(timezone.utc).isoformat(),
                    "downloaders": [],
                    "mediaservers": [],
                },
            )
            for spec in integrations:
                type_ = spec.get("type")
                bucket = {"downloader": "downloaders", "mediaserver": "mediaservers"}.get(
                    type_
                )
                if bucket is None:
                    logger.warning("未知的集成类型 %s，跳过", type_)
                    continue
                # from 为列表时取组内实际部署的那个来源应用
                sources = spec.get("from")
                if isinstance(sources, str):
                    sources = [sources]
                source_name = next(
                    (s for s in sources or [] if s in app_configs), None
                )
                if source_name is None:
                    continue
                record = await self._wire_one(
                    instance_name,
                    target_name,
                    target_cfg,
                    target_error,
                    type_,
                    source_name,
                    app_configs.get(source_name) or {},
                )
                results[bucket].append(record)

        if not target_results:
            return

        async with async_session() as db:
            group = await self.get_group(db, group_id)
            merged = dict(group.app_configs or {})
            for target_name, payload in target_results.items():
                entry = dict(merged.get(target_name) or {})
                # 幂等：每次重跑整体覆盖同名目标应用的装配结果
                entry["integrations"] = payload
                merged[target_name] = entry
            group.app_configs = merged
            await db.commit()

    async def _wire_one(
        self,
        instance_name: str,
        target_name: str,
        target_cfg: dict,
        target_error: str | None,
        type_: str,
        source_name: str,
        source_cfg: dict,
    ) -> dict:
        """装配单个来源应用，返回记录（name/type/url/status/message）。"""
        record = {"name": source_name, "type": source_name, "url": None}

        error = target_error or self._check_source(type_, source_cfg)
        if error:
            record.update(status="error", message=error)
            return record

        url = await self._resolve_integration_url(
            instance_name, target_name, source_name, source_cfg["url"]
        )
        record["url"] = url

        client = get_client(target_name)()
        try:
            if type_ == "downloader":
                ok, message = await client.setup_downloader(
                    target_cfg["url"].rstrip("/"),
                    target_cfg["api_key"],
                    name=source_name,
                    type_=source_name,
                    host=url,
                    username=source_cfg["username"],
                    password=source_cfg["password"],
                )
            else:
                ok, message = await client.setup_mediaserver(
                    target_cfg["url"].rstrip("/"),
                    target_cfg["api_key"],
                    name=source_name,
                    type_=source_name,
                    host=url,
                    api_key_ms=source_cfg["api_key"],
                    play_host=source_cfg["url"],
                )
        except Exception as exc:
            logger.exception("装配 %s -> %s 异常", source_name, target_name)
            ok, message = False, f"装配异常: {exc}"

        record["status"] = "ok" if ok else "error"
        record["message"] = message or ("装配成功" if ok else "装配失败")
        if ok and type_ == "mediaserver":
            # 媒体服务器侧需手动把 webhook 指回 MoviePilot（无稳定配置 API），
            # 记录建议的回调地址供前端展示给用户填写
            record["webhook_url"] = (
                f"{target_cfg['url'].rstrip('/')}/api/v1/webhook"
                f"?token={target_cfg['api_key']}"
            )
        return record

    @staticmethod
    def _check_target(target_cfg: dict) -> str | None:
        """目标应用前置条件检查，不满足返回原因。"""
        if not target_cfg.get("provisioned"):
            return "目标应用账号自动配置未完成"
        if not target_cfg.get("url"):
            return "目标应用缺少访问地址"
        if not target_cfg.get("api_key"):
            return "目标应用缺少 API Key"
        return None

    @staticmethod
    def _check_source(type_: str, source_cfg: dict) -> str | None:
        """来源应用前置条件检查，不满足返回原因。"""
        if not source_cfg.get("provisioned"):
            return "来源应用账号自动配置未完成"
        if not source_cfg.get("url"):
            return "来源应用缺少访问地址"
        if type_ == "downloader" and not (
            source_cfg.get("username") and source_cfg.get("password")
        ):
            return "来源应用缺少账号密码"
        if type_ == "mediaserver" and not source_cfg.get("api_key"):
            return "来源应用缺少 API Key"
        return None

    async def _resolve_integration_url(
        self,
        instance_name: str,
        target_name: str,
        source_name: str,
        source_url: str,
    ) -> str:
        """计算来源应用对目标应用可达的地址，按序候选并在目标容器内探测。

        候选顺序：
        a. 来源应用落库的内网访问地址（宿主内网 IP + 宿主端口，稳定可持久）；
        b. 两容器共享 Docker 网络时，``http://<来源容器名>:<来源容器内端口>``；
        c. 目标容器主网络 gateway IP + 来源宿主端口（网桥地址可能随
           网络重建变化，仅作最后兜底）。
        docker exec 探测不可用时跳过探测，直接用内网地址。
        """
        parsed = urlparse(source_url)
        host_port = parsed.port
        if not host_port:
            return source_url
        target_project = _slugify(f"{instance_name}-{target_name}")
        source_project = _slugify(f"{instance_name}-{source_name}")

        candidates: list[str] = [source_url]
        try:
            target_container = await asyncio.to_thread(
                self._get_project_container, target_project
            )
            source_container = await asyncio.to_thread(
                self._get_project_container, source_project
            )
        except Exception:
            logger.warning(
                "定位 %s/%s 容器失败，直接使用内网地址", target_project, source_project,
                exc_info=True,
            )
            return source_url

        if self._network_names(target_container) & self._network_names(source_container):
            container_port = await asyncio.to_thread(
                self._get_container_port, source_project, host_port
            )
            container_name = source_container.name.lstrip("/")
            candidates.append(f"http://{container_name}:{container_port or host_port}")
        gateway = self._container_gateway(target_container)
        if gateway:
            candidates.append(f"http://{gateway}:{host_port}")

        # 在目标容器内探测连通性，取第一个连通的候选
        for candidate in candidates:
            try:
                reachable = await asyncio.to_thread(
                    self._probe_from_container, target_container, candidate
                )
            except Exception:
                # exec 本身失败（如容器无 python）：跳过探测直接用内网地址
                logger.warning(
                    "容器 %s 内探测不可用，直接使用内网地址",
                    target_container.name,
                    exc_info=True,
                )
                return candidates[0]
            if reachable:
                return candidate
        # 探测均失败仍兜底内网地址，写入结果由装配调用反馈错误
        return source_url

    @staticmethod
    def _network_names(container) -> set[str]:
        """容器加入的 Docker 网络名集合。"""
        networks = (container.attrs.get("NetworkSettings") or {}).get("Networks") or {}
        return set(networks.keys())

    @staticmethod
    def _container_gateway(container) -> str | None:
        """容器主网络的 gateway IP（即宿主机在该网段的地址）。"""
        networks = (container.attrs.get("NetworkSettings") or {}).get("Networks") or {}
        for net in networks.values():
            gateway = net.get("Gateway")
            if gateway:
                return gateway
        return None

    @staticmethod
    def _probe_from_container(container, url: str) -> bool:
        """在目标容器内用 python urllib 探测地址连通性。"""
        code = (
            "import urllib.request;"
            f"urllib.request.urlopen({url!r}, timeout=5)"
        )
        result = container.exec_run(["python", "-c", code])
        return result.exit_code == 0
