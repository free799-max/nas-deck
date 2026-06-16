"""Docker 镜像业务服务。"""

import math
import urllib.parse

import httpx

from app.services import docker_common as common


class ImageService(common.BaseDockerService):
    """镜像管理服务，封装镜像列表、详情、搜索、拉取等。"""

    def list_images(self) -> list[dict]:
        """获取本地镜像列表（扁平化，每行对应一个 tag）。"""
        if not self._client:
            return []
        images = self._client.images.list()
        containers = self._client.containers.list(all=True)
        image_usage = {}
        for c in containers:
            img_id = c.image.id
            image_usage[img_id] = image_usage.get(img_id, 0) + 1

        result = []
        for img in images:
            attrs = img.attrs
            repo_tags = attrs.get("RepoTags") or []
            if not repo_tags:
                repo_tags = ["<none>:<none>"]

            full_id = img.id
            short_id = full_id.split(":")[-1][:12] if ":" in full_id else full_id[:12]
            container_count = image_usage.get(full_id, 0)

            for tag_str in repo_tags:
                if ":" in tag_str:
                    name, tag = tag_str.rsplit(":", 1)
                else:
                    name, tag = tag_str, "<none>"
                result.append({
                    "id": short_id,
                    "image_id": full_id,
                    "name": name,
                    "tag": tag,
                    "full_tag": tag_str,
                    "size": attrs.get("Size", 0),
                    "created": attrs.get("Created", ""),
                    "containers": container_count,
                })
        return result

    def get_image_detail(self, image_id: str) -> dict | None:
        """获取镜像完整元数据。"""
        if not self._client:
            return None
        try:
            image = self._client.images.get(image_id)
            attrs = image.attrs
            config = attrs.get("Config", {}) or {}
            rootfs = attrs.get("RootFS", {}) or {}
            history = attrs.get("History", []) or []

            exposed_ports = []
            ports = config.get("ExposedPorts", {})
            if ports:
                exposed_ports = list(ports.keys())

            volumes = []
            vols = config.get("Volumes", {})
            if vols:
                volumes = list(vols.keys())

            history_cmds = []
            for h in history:
                created_by = h.get("CreatedBy", "")
                if created_by:
                    history_cmds.append(created_by)

            layers = rootfs.get("Layers", []) or []

            repo_tags = attrs.get("RepoTags") or ["<none>:<none>"]
            first_tag = repo_tags[0]
            if ":" in first_tag:
                name, tag = first_tag.rsplit(":", 1)
            else:
                name, tag = first_tag, "<none>"

            parent = attrs.get("Parent") or None
            docker_version = attrs.get("DockerVersion") or None
            architecture = attrs.get("Architecture", "")
            os_value = attrs.get("Os", "")
            build = None
            if docker_version and os_value and architecture:
                build = f"Docker {docker_version} on {os_value}, {architecture}"

            layers_table = []
            try:
                for i, layer in enumerate(image.history()):
                    created_by = (layer.get("CreatedBy", "") or "").strip()
                    if not created_by:
                        continue
                    layers_table.append({
                        "order": i,
                        "size": layer.get("Size", 0) or 0,
                        "layer": created_by,
                    })
            except Exception:
                layers_table = []

            return {
                "id": attrs.get("Id", ""),
                "name": name,
                "tag": tag,
                "full_tag": first_tag,
                "size": attrs.get("Size", 0),
                "created": attrs.get("Created", ""),
                "architecture": architecture,
                "os": os_value,
                "cmd": config.get("Cmd"),
                "entrypoint": config.get("Entrypoint"),
                "env": config.get("Env"),
                "exposed_ports": exposed_ports or None,
                "volumes": volumes or None,
                "working_dir": config.get("WorkingDir") or None,
                "user": config.get("User") or None,
                "labels": config.get("Labels") or None,
                "layers": layers or None,
                "history": history_cmds or None,
                "parent": parent,
                "docker_version": docker_version,
                "build": build,
                "layers_table": layers_table or None,
            }
        except common.docker.errors.ImageNotFound:
            return None
        except Exception:
            return None

    def prune_unused_images(self) -> dict:
        """移除所有未使用的镜像。"""
        if not self._client:
            raise RuntimeError("Docker not available")
        result = self._client.images.prune(filters={"dangling": False})
        deleted_tags = [
            item["Untagged"]
            for item in result.get("ImagesDeleted", [])
            if "Untagged" in item
        ]
        return {
            "deleted": deleted_tags,
            "space_reclaimed": result.get("SpaceReclaimed", 0),
        }

    def remove_image(self, image_id: str, force: bool = False):
        """删除指定镜像。"""
        if not self._client:
            raise RuntimeError("Docker not available")
        self._client.images.remove(image_id, force=force)

    def remove_images(self, image_ids: list[str], force: bool = False) -> dict:
        """批量删除镜像。"""
        if not self._client:
            raise RuntimeError("Docker not available")
        deleted = []
        failed = []
        for image_id in image_ids:
            try:
                self._client.images.remove(image_id, force=force)
                deleted.append(image_id)
            except common.docker.errors.ImageNotFound:
                failed.append({"id": image_id, "reason": "镜像不存在"})
            except common.docker.errors.APIError as e:
                failed.append({"id": image_id, "reason": str(e)})
        return {"deleted": deleted, "failed": failed}

    def search_images(
        self,
        query: str,
        page: int = 1,
        api_url: str | None = None,
        mirror_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> dict:
        """搜索镜像。"""
        if not query.strip():
            return {"total": 0, "page": page, "page_size": 20, "results": []}

        auth = (username, password) if username and password else None
        page_size = 20

        def _parse_item(r: dict, field_map: dict[str, str]) -> dict:
            def _get(key: str, default=None):
                mapped = field_map.get(key, key)
                return r.get(mapped, r.get(key, default))

            return {
                "name": _get("name", ""),
                "description": _get("description", ""),
                "star_count": _get("star_count", 0),
                "pull_count": _get("pull_count", 0),
                "official": _get("official", False),
                "is_automated": _get("is_automated", False),
            }

        def _do_search(url: str, is_docker_hub: bool = False) -> dict:
            try:
                common.logger.info("镜像搜索请求: %s", url)
                resp = httpx.get(url, timeout=10, auth=auth)
                resp.raise_for_status()
                data = resp.json()
                if is_docker_hub:
                    results = data.get("results", [])
                    return {
                        "total": data.get("count", len(results)),
                        "page": page,
                        "page_size": page_size,
                        "results": [
                            _parse_item(r, {
                                "name": "repo_name",
                                "description": "short_description",
                                "official": "is_official",
                            })
                            for r in results
                        ],
                    }
                if isinstance(data, list):
                    return {
                        "total": len(data),
                        "page": page,
                        "page_size": page_size,
                        "results": [_parse_item(r, {}) for r in data],
                    }
                results = data.get("results", [])
                return {
                    "total": data.get("count", data.get("total", len(results))),
                    "page": data.get("page", page),
                    "page_size": data.get("page_size", page_size),
                    "results": [_parse_item(r, {}) for r in results],
                }
            except httpx.HTTPStatusError as e:
                msg = (
                    f"镜像搜索接口返回错误: {e.response.status_code} "
                    f"{e.response.reason_phrase} ({url})"
                )
                common.logger.error(msg)
                raise RuntimeError(msg) from e
            except httpx.RequestError as e:
                msg = f"镜像搜索接口请求失败: {e.__class__.__name__}: {e} ({url})"
                common.logger.error(msg)
                raise RuntimeError(msg) from e
            except Exception as e:
                msg = f"镜像搜索接口解析失败: {e.__class__.__name__}: {e} ({url})"
                common.logger.error(msg)
                raise RuntimeError(msg) from e

        def _build_search_url(base_url: str, is_docker_hub: bool) -> str:
            base = base_url.rstrip("/")
            if is_docker_hub:
                if not base.lower().endswith("/v2/search/repositories"):
                    base += "/v2/search/repositories"
                return (
                    base
                    + "?query="
                    + urllib.parse.quote(query.strip())
                    + f"&page_size={page_size}"
                    + f"&page={page}"
                )
            return base + "?search=" + urllib.parse.quote(query.strip())

        def _is_docker_hub_format(url: str) -> bool:
            url_lower = url.lower().rstrip("/")
            return (
                url_lower == "https://hub.docker.com"
                or url_lower == "https://registry.hub.docker.com"
                or url_lower.endswith("/v2/search/repositories")
                or url_lower.startswith("https://hub.docker.com")
                or url_lower.startswith("https://registry.hub.docker.com")
            )

        def _resolve_api_url(config_url: str | None) -> str | None:
            if not config_url:
                return None
            url = config_url.strip()
            if url.rstrip("/").lower() in (
                "https://hub.docker.com",
                "https://registry.hub.docker.com",
            ):
                return "https://hub.docker.com/v2/search/repositories"
            return url

        resolved_api = _resolve_api_url(api_url)
        resolved_mirror = _resolve_api_url(mirror_url)
        errors: list[str] = []

        if resolved_api:
            is_hub = _is_docker_hub_format(resolved_api)
            url = _build_search_url(resolved_api, is_hub)
            try:
                return _do_search(url, is_docker_hub=is_hub)
            except RuntimeError as e:
                errors.append(str(e))
            if resolved_mirror:
                is_hub = _is_docker_hub_format(resolved_mirror)
                url = _build_search_url(resolved_mirror, is_hub)
                try:
                    return _do_search(url, is_docker_hub=is_hub)
                except RuntimeError as e:
                    errors.append(str(e))
            raise RuntimeError("镜像搜索全部失败: " + "; ".join(errors))

        default_url = "https://hub.docker.com/v2/search/repositories"
        url = _build_search_url(default_url, is_docker_hub=True)
        try:
            return _do_search(url, is_docker_hub=True)
        except RuntimeError as e:
            raise RuntimeError("镜像搜索失败: " + str(e)) from e

    def pull_image(self, image: str):
        """拉取指定镜像。"""
        if not self._client:
            raise RuntimeError("Docker not available")
        self._client.images.pull(image)

    def get_image_tags(self, image: str) -> list[dict]:
        """获取指定镜像的可用标签列表。"""
        repo = image.strip()
        if "/" not in repo:
            repo = f"library/{repo}"

        url = f"https://hub.docker.com/v2/repositories/{repo}/tags/?page_size=100"
        try:
            resp = httpx.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            tags = []
            for r in results:
                tags.append({
                    "name": r.get("name", ""),
                    "last_updated": r.get("last_updated", ""),
                    "size": r.get("full_size", 0),
                    "digest": r.get("digest", ""),
                })
            return tags
        except Exception:
            return []

    def pull_image_async(self, image: str, task_id: str, task_manager):
        """在后台线程中流式拉取指定镜像，并报告进度。"""
        if not self._client:
            task_manager.fail_task(task_id, "Docker not available")
            raise RuntimeError("Docker not available")

        STATUS_MAP = {
            "Pulling from": "拉取中",
            "Pulling fs layer": "准备下载",
            "Waiting": "等待中",
            "Downloading": "下载中",
            "Download complete": "下载完成",
            "Verifying Checksum": "验证中",
            "Pull complete": "已完成",
            "Already exists": "已存在",
            "Layer already exists": "已存在",
            "Extracting": "解压中",
            "Pulling manifest": "获取清单",
        }

        def _format_bytes(b: int) -> str:
            if b == 0:
                return "0 B"
            k = 1024
            sizes = ["B", "KB", "MB", "GB", "TB"]
            i = min(len(sizes) - 1, int(math.log(b) / math.log(k)))
            return f"{b / (k ** i):.1f} {sizes[i]}"

        def _map_status(status: str) -> str:
            for key, value in STATUS_MAP.items():
                if key in status:
                    return value
            return status

        try:
            stream = self._client.api.pull(image, stream=True, decode=True)
            layers = {}
            last_progress_time = common.time.time()
            last_overall_percentage = 0

            for line in stream:
                if not line:
                    continue

                status = line.get("status", "")
                layer_id = line.get("id", "")
                progress_detail = line.get("progressDetail", {}) or {}
                current = progress_detail.get("current", 0) or 0
                total = progress_detail.get("total", 0) or 0

                now = common.time.time()

                if layer_id:
                    if layer_id not in layers:
                        layers[layer_id] = {
                            "status": status,
                            "current": current,
                            "total": total,
                            "last_current": current,
                            "last_time": now,
                            "speed": 0,
                        }
                    else:
                        old = layers[layer_id]
                        time_delta = now - old["last_time"]
                        if time_delta >= 0.5 and current > old["last_current"]:
                            speed = int((current - old["last_current"]) / time_delta)
                            old["speed"] = speed
                            old["last_current"] = current
                            old["last_time"] = now
                        old["status"] = status
                        old["current"] = current
                        if total > 0:
                            old["total"] = total

                layer_progress_list = []
                total_size = 0
                downloaded_size = 0
                total_speed = 0
                downloading_count = 0
                completed_layers = 0

                for lid, ldata in layers.items():
                    l_total = ldata.get("total", 0)
                    l_current = ldata.get("current", 0)
                    l_status = ldata.get("status", "")
                    l_speed = ldata.get("speed", 0)

                    completed_statuses = (
                        "Pull complete",
                        "Already exists",
                        "Layer already exists",
                        "Download complete",
                    )
                    l_percentage = 0
                    if l_status in completed_statuses:
                        l_percentage = 100
                    elif l_total > 0 and l_current > 0:
                        l_percentage = int((l_current / l_total) * 100)

                    if l_status in completed_statuses:
                        progress_text = "已完成"
                    elif l_total > 0:
                        progress_text = f"{_format_bytes(l_current)} / {_format_bytes(l_total)}"
                    else:
                        progress_text = "--"

                    layer_progress_list.append({
                        "id": lid,
                        "status": l_status,
                        "status_text": _map_status(l_status),
                        "current": l_current,
                        "total": l_total,
                        "progress_text": progress_text,
                        "percentage": l_percentage,
                        "speed": l_speed,
                    })

                    if l_status in completed_statuses or l_percentage == 100:
                        completed_layers += 1

                    if l_total > 0:
                        total_size += l_total
                        downloaded_size += min(l_current, l_total)

                    if l_speed > 0:
                        total_speed += l_speed
                        downloading_count += 1

                total_layers = len(layers)
                byte_percentage = 0
                if total_size > 0:
                    byte_percentage = int((downloaded_size / total_size) * 100)

                layer_average_percentage = 0
                if total_layers > 0:
                    layer_percentage_sum = sum(
                        layer["percentage"] for layer in layer_progress_list
                    )
                    layer_average_percentage = int(layer_percentage_sum / total_layers)

                calculated_percentage = max(byte_percentage, layer_average_percentage)
                percentage = max(calculated_percentage, last_overall_percentage)
                last_overall_percentage = percentage

                if downloading_count > 0:
                    overall_status = f"下载中 {downloading_count} 个层"
                elif completed_layers < total_layers:
                    overall_status = "准备下载"
                else:
                    overall_status = "处理中"

                size_text = (
                    f"{_format_bytes(downloaded_size)} / {_format_bytes(total_size)}"
                    if total_size > 0
                    else "--"
                )

                progress = {
                    "total_layers": total_layers,
                    "completed_layers": completed_layers,
                    "current_layer": layer_id,
                    "percentage": min(percentage, 99),
                    "status": overall_status,
                    "speed": total_speed,
                    "total_size": total_size,
                    "downloaded_size": downloaded_size,
                    "size_text": size_text,
                    "layers": layer_progress_list,
                }

                if now - last_progress_time >= 0.3:
                    task_manager.update_progress(task_id, progress)
                    last_progress_time = now

            task_manager.complete_task(task_id)
        except common.docker.errors.ImageNotFound:
            task_manager.fail_task(task_id, "镜像不存在")
        except common.docker.errors.APIError as e:
            task_manager.fail_task(task_id, f"拉取镜像失败: {e}")
        except Exception as e:
            task_manager.fail_task(task_id, f"拉取镜像失败: {e}")
