"""Docker Compose 编排核心服务。"""

import asyncio
import json
import logging
import re
import shutil
from pathlib import Path

import yaml

from app.config import settings
from app.models.docker import (
    COMPOSE_PROJECT_LABEL,
    DockerComposeProject,
    DockerComposeStack,
    DockerComposeVersion,
)
from app.models.orchestration import AppInstance
from app.services.compose.compose_discovery import ComposeDiscoveryService

logger = logging.getLogger(__name__)

# 允许的项目名字符：小写字母、数字、下划线、连字符
_PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")


class ComposeService:
    """Docker Compose 编排核心服务。

    负责 Compose 项目的文件落盘、CLI 调用和状态同步。
    """

    def __init__(self):
        """初始化 Compose 工作区目录。"""
        self.workspace = Path(settings.COMPOSE_WORKSPACE_DIR).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._locks: dict[int, asyncio.Lock] = {}
        self._docker_available: bool | None = None
        self._discovery = ComposeDiscoveryService()

    @property
    def docker_available(self) -> bool:
        """检查 docker 命令是否可用（结果缓存一次）。"""
        if self._docker_available is None:
            self._docker_available = shutil.which("docker") is not None
        return self._docker_available

    def _project_dir(self, project_name: str) -> Path:
        """获取系统创建项目的目录路径。"""
        return self.workspace / project_name

    def _compose_file(self, project_name: str) -> Path:
        """获取系统创建项目的默认 docker-compose.yml 路径。"""
        return self._project_dir(project_name) / "docker-compose.yml"

    def _config_files(self, project: DockerComposeProject) -> list[Path]:
        """解析项目的 compose 文件路径列表。"""
        if project.config_files:
            try:
                paths = json.loads(project.config_files)
                if isinstance(paths, list) and paths:
                    return [Path(p) for p in paths]
            except json.JSONDecodeError:
                pass
        return [self._compose_file(project.project_name)]

    def _working_dir(self, project: DockerComposeProject) -> Path:
        """解析项目执行工作目录。"""
        if project.working_dir:
            return Path(project.working_dir)
        return self._project_dir(project.project_name)

    def _lock(self, project_id: int) -> asyncio.Lock:
        """获取项目级操作锁。"""
        if project_id not in self._locks:
            self._locks[project_id] = asyncio.Lock()
        return self._locks[project_id]

    @staticmethod
    def validate_project_name(project_name: str) -> None:
        """校验项目名是否合法。"""
        if not project_name:
            raise ValueError("项目名不能为空")
        if not _PROJECT_NAME_PATTERN.match(project_name):
            raise ValueError("项目名只能包含小写字母、数字、下划线和连字符")

    @staticmethod
    def validate_yaml(content: str) -> None:
        """校验 YAML 内容是否合法。"""
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 格式错误: {e}") from e

    @staticmethod
    def _inject_labels(content: str, project_name: str) -> str:
        """在 YAML 中为每个服务注入 Compose 项目归属标签。"""
        data = yaml.safe_load(content) or {}
        services = data.get("services")
        if not isinstance(services, dict):
            return content

        label_key = COMPOSE_PROJECT_LABEL
        label_value = project_name
        for svc_name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            labels = svc.setdefault("labels", [])
            if isinstance(labels, dict):
                labels[label_key] = label_value
            elif isinstance(labels, list):
                exists = any(
                    (
                        isinstance(item, str)
                        and item.startswith(f"{label_key}=")
                    )
                    or (
                        isinstance(item, dict)
                        and item.get(label_key) is not None
                    )
                    for item in labels
                )
                if not exists:
                    labels.append(f"{label_key}={label_value}")
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    async def _write_compose_file(
        self, project: DockerComposeProject, version: DockerComposeVersion
    ) -> Path:
        """将当前版本 YAML 写入项目工作目录。"""
        config_files = self._config_files(project)
        compose_file = config_files[0]
        working_dir = self._working_dir(project)
        working_dir.mkdir(parents=True, exist_ok=True)
        content = self._inject_labels(version.content, project.project_name)
        compose_file.write_text(content, encoding="utf-8")
        return compose_file

    async def _run(
        self,
        project: DockerComposeProject,
        *args: str,
        timeout: int = 120,
    ) -> dict:
        """执行 docker compose CLI 命令。"""
        if not self.docker_available:
            raise RuntimeError("未找到 docker 命令，请确认 Docker 已安装")

        config_files = self._config_files(project)
        working_dir = self._working_dir(project)

        cmd = ["docker", "compose"]
        for cf in config_files:
            cmd.extend(["-f", str(cf)])
        cmd.extend(["-p", project.project_name, *args])

        logger.info("执行 compose 命令: %s (cwd=%s)", " ".join(cmd), working_dir)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError("docker compose 命令执行超时")

        return {
            "returncode": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }

    @staticmethod
    def _ensure_host_directories(content: str) -> None:
        """解析 Compose YAML，为 bind mount 的宿主机路径自动创建目录。"""
        try:
            data = yaml.safe_load(content) or {}
        except yaml.YAMLError:
            return

        services = data.get("services") or {}
        host_paths: set[str] = set()

        for svc in services.values():
            if not isinstance(svc, dict):
                continue
            volumes = svc.get("volumes") or []
            if not isinstance(volumes, list):
                continue
            for vol in volumes:
                source: str | None = None
                if isinstance(vol, str):
                    # 短语法：source:target[:mode]
                    parts = vol.split(":")
                    if parts:
                        source = parts[0].strip()
                elif isinstance(vol, dict):
                    # 长语法
                    if vol.get("type") == "bind" or "source" in vol:
                        source = vol.get("source")
                        if not source and "bind" in vol:
                            source = vol["bind"].get("source")
                if source and source.startswith("/"):
                    host_paths.add(source)

        for path_str in host_paths:
            try:
                Path(path_str).mkdir(parents=True, exist_ok=True)
            except OSError:
                # 权限不足或路径非法时跳过，避免阻塞部署
                logger.warning("自动创建宿主机目录失败: %s", path_str)

    async def create_project(
        self,
        db,
        project_name: str,
        content: str,
        user_id: int | None = None,
        description: str | None = None,
    ) -> DockerComposeProject:
        """创建 Compose 项目并写入初始版本。"""
        self.validate_project_name(project_name)
        self.validate_yaml(content)

        # 自动创建 bind mount 所需的宿主机目录
        self._ensure_host_directories(content)

        project_dir = self._project_dir(project_name)
        project_dir.mkdir(parents=True, exist_ok=True)
        compose_file = self._compose_file(project_name)

        project = DockerComposeProject(
            project_name=project_name,
            description=description,
            config_files=json.dumps([str(compose_file)], ensure_ascii=False),
            working_dir=str(project_dir),
        )
        db.add(project)
        await db.flush()

        version = DockerComposeVersion(
            project_id=project.id,
            version_number=1,
            content=content,
            comment=None,
            is_current=True,
            created_by_user_id=user_id,
        )
        db.add(version)
        await db.flush()

        await self._write_compose_file(project, version)

        result = await self._run(project, "up", "-d", timeout=300)
        if result["returncode"] != 0:
            raise RuntimeError(f"项目创建后部署失败: {result['stderr']}")

        stack = await self.sync_stack_status(db, project, action="up")
        if stack.service_count > 0 and stack.running_count == 0:
            raise RuntimeError(
                "服务启动后未保持运行，请检查容器日志或 compose 配置"
            )

        await db.commit()
        await db.refresh(project)
        return project

    async def update_project(
        self,
        db,
        project: DockerComposeProject,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> DockerComposeProject:
        """更新项目元数据。"""
        if description is not None:
            project.description = description
        if is_active is not None:
            project.is_active = is_active
        await db.commit()
        await db.refresh(project)
        return project

    async def delete_project(
        self, db, project: DockerComposeProject
    ) -> None:
        """删除项目。"""
        async with self._lock(project.id):
            try:
                await self._run(project, "down", "--remove-orphans", timeout=120)
            except Exception as e:
                logger.warning("删除项目时 down 失败（可能已不存在）: %s", e)

            project_dir = self._project_dir(project.project_name)
            if project_dir == self._working_dir(project):
                if project_dir.exists():
                    shutil.rmtree(project_dir)

            # 先清理关联的应用实例记录（含备份级联删除）
            from sqlalchemy import delete

            await db.execute(
                delete(AppInstance).where(AppInstance.project_id == project.id)
            )

            await db.delete(project)
            await db.commit()
            self._locks.pop(project.id, None)

    async def add_version(
        self,
        db,
        project: DockerComposeProject,
        content: str,
        user_id: int | None = None,
    ) -> DockerComposeVersion:
        """为项目新增一个版本并设为当前版本。"""
        from sqlalchemy import select, update

        self.validate_yaml(content)

        result = await db.execute(
            select(DockerComposeVersion.version_number)
            .where(DockerComposeVersion.project_id == project.id)
            .order_by(DockerComposeVersion.version_number.desc())
        )
        max_version = result.scalar() or 0

        await db.execute(
            update(DockerComposeVersion)
            .where(DockerComposeVersion.project_id == project.id)
            .values(is_current=False)
        )

        version = DockerComposeVersion(
            project_id=project.id,
            version_number=max_version + 1,
            content=content,
            comment=None,
            is_current=True,
            created_by_user_id=user_id,
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)

        await self._write_compose_file(project, version)
        return version

    async def edit_and_deploy(
        self,
        db,
        project: DockerComposeProject,
        content: str,
        user_id: int | None = None,
        comment: str | None = None,
        description: str | None = None,
    ) -> tuple[DockerComposeVersion, dict]:
        """编辑 Compose 项目：保存新版本并自动部署。"""
        from sqlalchemy import select, update

        self.validate_yaml(content)

        async with self._lock(project.id):
            if description is not None:
                project.description = description

            result = await db.execute(
                select(DockerComposeVersion.version_number)
                .where(DockerComposeVersion.project_id == project.id)
                .order_by(DockerComposeVersion.version_number.desc())
            )
            max_version = result.scalar() or 0

            await db.execute(
                update(DockerComposeVersion)
                .where(DockerComposeVersion.project_id == project.id)
                .values(is_current=False)
            )

            version = DockerComposeVersion(
                project_id=project.id,
                version_number=max_version + 1,
                content=content,
                comment=comment or "编辑更新",
                is_current=True,
                created_by_user_id=user_id,
            )
            db.add(version)
            await db.commit()
            await db.refresh(version)

            await self._write_compose_file(project, version)
            result = await self._run(project, "up", "-d", timeout=300)
            if result["returncode"] != 0:
                raise RuntimeError(f"编辑后部署失败: {result['stderr']}")

            stack = await self.sync_stack_status(db, project, action="up")
            if stack.service_count > 0 and stack.running_count == 0:
                raise RuntimeError(
                    "服务启动后未保持运行，请检查容器日志或 compose 配置"
                )

            return version, result

    async def rollback_version(
        self,
        db,
        project: DockerComposeProject,
        version: DockerComposeVersion,
    ) -> DockerComposeVersion:
        """切换到指定版本。"""
        from sqlalchemy import update

        async with self._lock(project.id):
            await db.execute(
                update(DockerComposeVersion)
                .where(DockerComposeVersion.project_id == project.id)
                .values(is_current=False)
            )
            version.is_current = True
            await db.commit()
            await db.refresh(version)

            await self._write_compose_file(project, version)
            result = await self._run(project, "up", "-d", timeout=300)
            if result["returncode"] != 0:
                raise RuntimeError(f"切换后启动失败: {result['stderr']}")

            await self.sync_stack_status(db, project, action="rollback")
            return version

    async def action(
        self,
        db,
        project: DockerComposeProject,
        action: str,
    ) -> dict:
        """对项目执行 up / down / restart 操作。"""
        if action not in {"up", "down", "restart"}:
            raise ValueError(f"不支持的操作: {action}")

        async with self._lock(project.id):
            if action == "up":
                result = await self._run(project, "up", "-d", timeout=300)
            elif action == "down":
                result = await self._run(
                    project, "down", "--remove-orphans", timeout=120
                )
            else:
                result = await self._run(project, "restart", timeout=120)

            if result["returncode"] != 0:
                raise RuntimeError(result["stderr"])

            stack = await self.sync_stack_status(db, project, action=action)
            if action == "up" and stack.service_count > 0 and stack.running_count == 0:
                raise RuntimeError(
                    "服务启动后未保持运行，请检查容器日志或 compose 配置"
                )
            return result

    async def get_logs(
        self,
        project: DockerComposeProject,
        tail: int = 100,
        services: list[str] | None = None,
    ) -> str:
        """获取项目日志。"""
        args = ["logs", "--tail", str(tail)]
        if services:
            args.extend(services)
        result = await self._run(project, *args, timeout=60)
        if result["returncode"] != 0:
            raise RuntimeError(result["stderr"])
        return result["stdout"]

    async def stream_logs(
        self,
        project: DockerComposeProject,
        tail: int = 100,
        services: list[str] | None = None,
        follow: bool = True,
    ):
        """流式获取项目日志。"""
        if not self.docker_available:
            raise RuntimeError("未找到 docker 命令，请确认 Docker 已安装")

        config_files = self._config_files(project)
        working_dir = self._working_dir(project)

        cmd = ["docker", "compose"]
        for cf in config_files:
            cmd.extend(["-f", str(cf)])
        cmd.extend(["-p", project.project_name, "logs", "--tail", str(tail)])
        if follow:
            cmd.append("-f")
        if services:
            cmd.extend(services)

        logger.info("执行 compose 日志流: %s (cwd=%s)", " ".join(cmd), working_dir)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir),
        )
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield line.decode("utf-8", errors="replace").rstrip("\n")

            stderr_data = await proc.stderr.read()
            stderr = stderr_data.decode("utf-8", errors="replace").strip()
            if stderr:
                logger.warning("compose 日志流 stderr: %s", stderr)
        finally:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()

    async def get_status(
        self, project: DockerComposeProject
    ) -> dict:
        """获取项目实时服务状态。"""
        result = await self._run(project, "ps", "--format", "json", timeout=30)
        if result["returncode"] != 0:
            raise RuntimeError(result["stderr"])

        try:
            services = []
            for line in (result["stdout"] or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    services.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except Exception:
            services = []

        return self._parse_ps(services)

    @staticmethod
    def _parse_ps(services: list) -> dict:
        """解析 docker compose ps --format json 输出。"""
        total = len(services)
        running = 0
        port_set: set[str] = set()
        for svc in services:
            state = svc.get("State", "")
            if state == "running":
                running += 1
            publishers = svc.get("Publishers") or []
            for pub in publishers:
                url = pub.get("URL", "")
                target = pub.get("TargetPort", "")
                published = pub.get("PublishedPort", "")
                if url and target and published:
                    port_set.add(f"{url}:{published}->{target}")

        if total == 0:
            status = "stopped"
        elif running == total:
            status = "running"
        elif running > 0:
            status = "partial"
        else:
            status = "exited"

        return {
            "status": status,
            "service_count": total,
            "running_count": running,
            "ports": sorted(port_set),
        }

    async def sync_stack_status(
        self,
        db,
        project: DockerComposeProject,
        action: str | None = None,
    ) -> DockerComposeStack:
        """同步 Stack 状态到数据库。"""
        from datetime import datetime
        from sqlalchemy import select

        status_info = await self.get_status(project)
        result = await db.execute(
            select(DockerComposeStack).where(
                DockerComposeStack.project_id == project.id
            )
        )
        stack = result.scalar_one_or_none()
        if not stack:
            stack = DockerComposeStack(project_id=project.id)
            db.add(stack)

        stack.status = status_info["status"]
        stack.service_count = status_info["service_count"]
        stack.running_count = status_info["running_count"]
        stack.ports = json.dumps(status_info["ports"], ensure_ascii=False)
        if action:
            stack.last_action = action
            stack.last_action_at = datetime.now()
        stack.updated_at = datetime.now()

        await db.commit()
        await db.refresh(stack)
        return stack

    async def discover_projects(self, db) -> list[DockerComposeProject]:
        """委托给自动发现服务扫描 Docker 容器并补全项目记录。"""
        return await self._discovery.discover_projects(db)


# 全局单例
compose_manager = ComposeService()
