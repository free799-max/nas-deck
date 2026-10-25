"""代理连通性检测服务。

用（可选的）HTTP/HTTPS 代理并发访问一组常用境外站点，
返回每个站点的连通状态与服务端响应耗时。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.core.exceptions import APIException

PROXY_TEST_TIMEOUT = 8.0
"""单个站点的请求超时（秒）。"""

PROXY_TEST_SITES: tuple[tuple[str, str], ...] = (
    ("百度", "https://www.baidu.com"),
    ("Google", "https://www.google.com/generate_204"),
    ("GitHub", "https://github.com/robots.txt"),
    ("Telegram", "https://telegram.org"),
    ("YouTube", "https://www.youtube.com/generate_204"),
)


def normalize_proxy_url(raw: str | None) -> str | None:
    """校验并规范化代理地址；空值返回 None。

    Args:
        raw: 用户填写的代理地址

    Returns:
        str | None: 规范化后的地址，未填写时为 None

    Raises:
        APIException: 协议不是 http/https 或长度超限
    """
    value = (raw or "").strip()
    if not value:
        return None
    if not value.lower().startswith(("http://", "https://")):
        raise APIException("代理地址必须以 http:// 或 https:// 开头", 400)
    if len(value) > 500:
        raise APIException("代理地址长度不能超过 500 个字符", 400)
    return value


class ProxyTestService:
    """代理连通性检测服务。"""

    async def test(
        self,
        http_proxy: str | None = None,
        https_proxy: str | None = None,
    ) -> dict[str, Any]:
        """检测常用境外站点在当前代理下的连通性。

        HTTPS 代理优先，其次 HTTP 代理；两者都为空时直接连接（不走代理）。

        Args:
            http_proxy: HTTP 代理地址
            https_proxy: HTTPS 代理地址

        Returns:
            dict: 实际使用的代理、成功数量与逐站点结果
        """
        proxy = normalize_proxy_url(https_proxy) or normalize_proxy_url(http_proxy)
        async with httpx.AsyncClient(
            proxy=proxy,
            trust_env=False,
            timeout=PROXY_TEST_TIMEOUT,
            follow_redirects=True,
        ) as client:
            results = await asyncio.gather(
                *(self._probe(client, proxy, name, url) for name, url in PROXY_TEST_SITES)
            )
        return {
            "proxy": proxy,
            "ok_count": sum(1 for item in results if item["ok"]),
            "total": len(results),
            "results": list(results),
        }

    async def _probe(
        self,
        client: httpx.AsyncClient,
        proxy: str | None,
        name: str,
        url: str,
    ) -> dict[str, Any]:
        """请求单个站点，只等响应头即断开，避免下载页面内容。"""
        started = time.perf_counter()
        try:
            request = client.build_request("GET", url)
            response = await client.send(request, stream=True)
            try:
                status_code = response.status_code
            finally:
                await response.aclose()
            return {
                "name": name,
                "url": url,
                "ok": True,
                "status_code": status_code,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 — 任何网络异常都算该站点不可用
            message = str(exc) or exc.__class__.__name__
            if proxy:
                message = message.replace(proxy, "<代理>")
            return {
                "name": name,
                "url": url,
                "ok": False,
                "status_code": None,
                "latency_ms": None,
                "error": message[:200],
            }


# 全局服务单例
proxy_test_service = ProxyTestService()
