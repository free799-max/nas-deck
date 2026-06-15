"""Docker Compose 编排管理器模块。

提供 Docker Compose 项目的生命周期管理：
- 项目/版本 CRUD
- 版本回退
- 通过 docker compose CLI 执行 up/down/restart/logs/ps
- Stack 状态同步到数据库
- 自动发现系统外通过 docker compose 启动的项目

设计要点：
- 当前激活版本通过 DockerComposeVersion.is_current 标识，避免循环外键。
- 每个项目记录真实 config_files 与 working_dir，支持系统创建与外部发现项目统一维护。
- 发现机制扫描容器标准标签 com.docker.compose.project，自动补全数据库记录。
- 所有 CLI 调用均使用 asyncio 子进程，避免阻塞事件循环。
"""

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
from app.core.docker_manager import docker_manager

logger = logging.getLogger(__name__)

# 允许的项目名字符：小写字母、数字、下划线、连字符
_PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")

# Docker Compose 标准项目标签
_DOCKER_COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
_DOCKER_COMPOSE_CONFIG_FILES_LABEL = "com.docker.compose.project.config_files"
_DOCKER_COMPOSE_WORKING_DIR_LABEL = "com.docker.compose.project.working_dir"


class ComposeManager:
    """Docker Compose 编排管理器。

    负责 Compose 项目的文件落盘、CLI 调用和状态同步。

    Attributes:
        workspace: Compose 工作区根目录（系统创建项目默认落盘位置）。
        _locks: 项目级异步锁，防止同一项目并发操作。
    """

    def __init__(self):
        """初始化 Compose 工作区目录并检测 docker 命令。"""
        self.workspace = Path(settings.COMPOSE_WORKSPACE_DIR).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._locks: dict[int, asyncio.Lock] = {}
        self._docker_available: bool | None = None

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
        """解析项目的 compose 文件路径列表。

        若项目未保存路径（旧数据兼容），返回 workspace 下默认路径。
        """
        if project.config_files:
            try:
                paths = json.loads(project.config_files)
                if isinstance(paths, list) and paths:
                    return [Path(p) for p in paths]
            except json.JSONDecodeError:
                pass
        return [self._compose_file(project.project_name)]

    def _working_dir(self, project: DockerComposeProject) -> Path:
        """解析项目执行工作目录。

        若项目未保存工作目录（旧数据兼容），返回 workspace 下项目目录。
        """
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
        """校验项目名是否合法。

        项目名只能包含小写字母、数字、下划线和连字符。

        Raises:
            ValueError: 当项目名不合法时抛出。
        """
        if not project_name:
            raise ValueError("项目名不能为空")
        if not _PROJECT_NAME_PATTERN.match(project_name):
            raise ValueError("项目名只能包含小写字母、数字、下划线和连字符")

    @staticmethod
    def validate_yaml(content: str) -> None:
        """校验 YAML 内容是否合法。

        Raises:
            ValueError: 当 YAML 解析失败时抛出。
        """
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 格式错误: {e}") from e

    @staticmethod
    def _inject_labels(content: str, project_name: str) -> str:
        """在 YAML 中为每个服务注入 Compose 项目归属标签。

        该标签仅用于运行时识别，不修改数据库中保存的原始 YAML。

        Args:
            content: 原始 YAML 内容。
            project_name: 项目名。

        Returns:
            str: 注入标签后的 YAML 内容。
        """
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
        """将当前版本 YAML 写入项目工作目录/指定路径。

        Args:
            project: Compose 项目对象。
            version: 要写入的版本对象。

        Returns:
            Path: 写入后的主文件路径。
        """
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
        """执行 docker compose CLI 命令。

        Args:
            project: Compose 项目对象。
            *args: 传递给 docker compose 的子命令及参数。
            timeout: 超时时间（秒）。

        Returns:
            dict: 包含 returncode、stdout、stderr 的字典。

        Raises:
            RuntimeError: 当命令执行超时或 docker 命令不存在时抛出。
        """
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

    async def create_project(
        self,
        db,
        project_name: str,
        content: str,
        user_id: int | None = None,
        description: str | None = None,
    ) -> DockerComposeProject:
        """创建 Compose 项目并写入初始版本。

        Args:
            db: 数据库异步会话。
            project_name: CLI 项目名。
            content: 初始 YAML 内容。
            user_id: 创建用户 ID。
            description: 项目描述。

        Returns:
            DockerComposeProject: 创建的项目对象。

        Raises:
            ValueError: 当项目名不合法或 YAML 格式错误时抛出。
        """
        self.validate_project_name(project_name)
        self.validate_yaml(content)

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
        await db.flush()  # 获取 project.id

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

        # 创建后立即部署
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
        """更新项目元数据。

        Args:
            db: 数据库异步会话。
            project: 项目对象。
            description: 项目描述。
            is_active: 是否启用。

        Returns:
            DockerComposeProject: 更新后的项目对象。
        """
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
        """删除项目。

        先执行 docker compose down 清理容器/网络，再删除工作目录和数据库记录。
        外部发现的项目只删除数据库记录，不删除源文件目录。

        Args:
            db: 数据库异步会话。
            project: 项目对象。
        """
        async with self._lock(project.id):
            try:
                await self._run(project, "down", "--remove-orphans", timeout=120)
            except Exception as e:
                logger.warning("删除项目时 down 失败（可能已不存在）: %s", e)

            project_dir = self._project_dir(project.project_name)
            # 仅删除系统创建项目的工作目录，避免误删外部项目源目录
            if project_dir == self._working_dir(project):
                if project_dir.exists():
                    shutil.rmtree(project_dir)

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
        """为项目新增一个版本并设为当前版本。

        Args:
            db: 数据库异步会话。
            project: 项目对象。
            content: YAML 内容。
            user_id: 创建用户 ID。

        Returns:
            DockerComposeVersion: 新增的版本对象。
        """
        from sqlalchemy import select, update

        self.validate_yaml(content)

        # 查询当前最大版本号
        result = await db.execute(
            select(DockerComposeVersion.version_number)
            .where(DockerComposeVersion.project_id == project.id)
            .order_by(DockerComposeVersion.version_number.desc())
        )
        max_version = result.scalar() or 0

        # 旧版本全部取消 current
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
        """编辑 Compose 项目：保存新版本并自动部署。

        整个流程在项目锁内执行，包括 YAML 校验、版本生成、文件落盘、
        docker compose up -d 以及状态同步。

        Args:
            db: 数据库异步会话。
            project: Compose 项目对象。
            content: 更新后的 YAML 内容。
            user_id: 创建用户 ID。
            comment: 版本说明，为空时默认"编辑更新"。
            description: 项目描述，为空时保持不变。

        Returns:
            tuple[DockerComposeVersion, dict]: 新增的版本对象和 CLI 执行结果。

        Raises:
            ValueError: YAML 格式错误。
            RuntimeError: docker compose up 执行失败或服务未保持运行。
        """
        from sqlalchemy import select, update

        self.validate_yaml(content)

        async with self._lock(project.id):
            if description is not None:
                project.description = description

            # 查询当前最大版本号
            result = await db.execute(
                select(DockerComposeVersion.version_number)
                .where(DockerComposeVersion.project_id == project.id)
                .order_by(DockerComposeVersion.version_number.desc())
            )
            max_version = result.scalar() or 0

            # 旧版本全部取消 current
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
        """切换到指定版本。

        将目标版本设为当前版本，重写 compose 文件，并自动执行 up -d 应用。

        Args:
            db: 数据库异步会话。
            project: 项目对象。
            version: 目标版本对象。

        Returns:
            DockerComposeVersion: 切换后的当前版本对象。
        """
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
        """对项目执行 up / down / restart 操作。

        Args:
            db: 数据库异步会话。
            project: 项目对象。
            action: 操作类型。

        Returns:
            dict: CLI 执行结果。

        Raises:
            ValueError: 当 action 不合法时抛出。
            RuntimeError: 当 CLI 执行失败时抛出。
        """
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
            # up 操作需要确认至少有一个服务处于运行状态，避免 CLI 返回 0 但服务启动后立即退出
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
        """获取项目日志。

        Args:
            project: 项目对象。
            tail: 返回最后 N 行日志。
            services: 指定服务列表，为空则获取全部服务日志。

        Returns:
            str: 日志文本。
        """
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
        """流式获取项目日志。

        通过 docker compose logs -f 实时读取日志行，适用于 SSE 推送。

        Args:
            project: 项目对象。
            tail: 返回最后 N 行日志。
            services: 指定服务列表，为空则获取全部服务日志。
            follow: 是否持续跟踪新日志。

        Yields:
            str: 单条日志行。
        """
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

            # 命令结束时检查 stderr
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
        """获取项目实时服务状态。

        Returns:
            dict: 包含服务列表、状态、端口等信息的字典。
        """
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
        """解析 docker compose ps --format json 输出。

        Args:
            services: JSON 解析后的服务容器列表。

        Returns:
            dict: 包含 status、service_count、running_count、ports 的字典。
        """
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
        """同步 Stack 状态到数据库。

        Args:
            db: 数据库异步会话。
            project: 项目对象。
            action: 触发同步的操作类型，可选。

        Returns:
            DockerComposeStack: 更新后的 Stack 状态对象。
        """
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
        """扫描 Docker 容器，自动发现/补全 Compose 项目记录。

        通过标准标签 com.docker.compose.project 识别项目，
        对未入库项目创建记录并尝试读取当前 compose 文件内容作为初始版本。

        Args:
            db: 数据库异步会话。

        Returns:
            list[DockerComposeProject]: 所有项目记录（含新发现的）。
        """
        from sqlalchemy import select

        if not docker_manager.available:
            result = await db.execute(
                select(DockerComposeProject).order_by(DockerComposeProject.id.desc())
            )
            return result.scalars().all()

        containers = docker_manager.list_containers()
        projects_map: dict[str, dict] = {}
        for c in containers:
            labels = c.get("labels") or {}
            if not isinstance(labels, dict):
                continue
            project_name = labels.get(_DOCKER_COMPOSE_PROJECT_LABEL)
            if not project_name:
                continue
            if project_name not in projects_map:
                projects_map[project_name] = {
                    "config_files": set(),
                    "working_dir": labels.get(_DOCKER_COMPOSE_WORKING_DIR_LABEL, ""),
                }
            config_files = labels.get(_DOCKER_COMPOSE_CONFIG_FILES_LABEL, "")
            if config_files:
                for cf in config_files.split(","):
                    cf = cf.strip()
                    if cf:
                        projects_map[project_name]["config_files"].add(cf)

        # 从数据库查询现有项目
        result = await db.execute(select(DockerComposeProject))
        existing = {p.project_name: p for p in result.scalars().all()}

        discovered: list[DockerComposeProject] = []
        for project_name, info in projects_map.items():
            config_files = sorted(info["config_files"])
            working_dir = info["working_dir"]
            if project_name in existing:
                project = existing[project_name]
                # 补全/更新路径信息
                if config_files and not project.config_files:
                    project.config_files = json.dumps(config_files, ensure_ascii=False)
                if working_dir and not project.working_dir:
                    project.working_dir = working_dir
                discovered.append(project)
                continue

            # 新建外部发现项目
            project = DockerComposeProject(
                project_name=project_name,
                description=None,
                config_files=json.dumps(config_files, ensure_ascii=False) if config_files else None,
                working_dir=working_dir or None,
            )
            db.add(project)
            await db.flush()

            # 尝试读取当前 compose 文件作为初始版本
            if config_files:
                first_file = Path(config_files[0])
                if first_file.exists():
                    try:
                        content = first_file.read_text(encoding="utf-8")
                        self.validate_yaml(content)
                        version = DockerComposeVersion(
                            project_id=project.id,
                            version_number=1,
                            content=content,
                            comment=None,
                            is_current=True,
                            created_by_user_id=None,
                        )
                        db.add(version)
                    except Exception as e:
                        logger.warning(
                            "读取外部项目 %s 的 compose 文件失败: %s", project_name, e
                        )

            discovered.append(project)

        await db.commit()
        # 刷新对象关系
        for p in discovered:
            await db.refresh(p)
        return discovered


# 全局单例
compose_manager = ComposeManager()
