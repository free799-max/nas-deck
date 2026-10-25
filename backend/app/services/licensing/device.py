"""基于 Docker Engine 的授权设备指纹。"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import docker


def _docker_engine_info() -> dict[str, Any]:
    client = docker.from_env()
    try:
        return client.info()
    finally:
        client.close()


def _read_cpu_model() -> str | None:
    models: dict[str, str] = {}
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo:
            for line in cpuinfo:
                key, separator, value = line.partition(":")
                normalized_key = key.strip().lower()
                model = value.strip()
                if (
                    separator
                    and normalized_key in {"model name", "hardware", "processor"}
                    and normalized_key not in models
                    and model
                ):
                    models[normalized_key] = model
    except OSError:
        pass
    return next((models[key] for key in ("model name", "hardware", "processor") if key in models), None)


async def get_device_fingerprint(installation_id: str) -> dict[str, Any]:
    device_info = {
        "cpu_model": None,
        "cpu_cores": None,
        "memory_total_bytes": None,
    }
    try:
        engine_info = await asyncio.to_thread(_docker_engine_info)
        engine_id = engine_info.get("ID")
        if not isinstance(engine_id, str) or not engine_id.strip():
            raise ValueError("Docker Engine ID is missing")
        device_info["cpu_model"] = _read_cpu_model()
        device_info["cpu_cores"] = engine_info.get("NCPU")
        device_info["memory_total_bytes"] = engine_info.get("MemTotal")
        fingerprint = hashlib.sha256(f"docker:{engine_id.strip()}".encode()).hexdigest()
        source = "docker"
    except Exception:
        fingerprint = hashlib.sha256(f"installation:{installation_id}".encode()).hexdigest()
        source = "installation"
    return {
        "hardware_fingerprint": fingerprint,
        "fingerprint_source": source,
        "device_info": device_info,
    }
