import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from app.core.compose_manager import ComposeManager
from app.models.docker import DockerComposeProject, DockerComposeVersion


@pytest.fixture
def compose_manager():
    return ComposeManager()


@pytest.mark.asyncio
async def test_discover_projects_creates_external_project(compose_manager, tmp_path):
    """发现系统外 Compose 项目时自动创建数据库记录。"""
    # 模拟容器标签
    mock_container = {
        "id": "abc123",
        "name": "keygen-api-web-1",
        "status": "running",
        "state": "运行中",
        "health": "unknown",
        "image": "keygen-api:latest",
        "ports": "8080:8080",
        "created": "2026-01-01T00:00:00Z",
        "labels": {
            "com.docker.compose.project": "keygen-api",
            "com.docker.compose.project.config_files": str(tmp_path / "compose.yaml"),
            "com.docker.compose.project.working_dir": str(tmp_path),
        },
    }

    # 创建临时 compose 文件
    compose_file = tmp_path / "compose.yaml"
    compose_file.write_text("services:\n  web:\n    image: nginx:latest\n")

    with patch(
        "app.core.compose_manager.docker_manager.list_containers",
        return_value=[mock_container],
    ):
        # 模拟异步数据库会话
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        projects = await compose_manager.discover_projects(db)

    assert len(projects) == 1
    project = projects[0]
    assert project.project_name == "keygen-api"
    assert project.working_dir == str(tmp_path)
    db.add.assert_called()
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_config_files_returns_default_for_legacy_project(compose_manager, tmp_path):
    """旧项目未保存 config_files 时返回 workspace 默认路径。"""
    project = MagicMock()
    project.project_name = "legacy"
    project.config_files = None
    project.working_dir = None

    paths = compose_manager._config_files(project)
    working_dir = compose_manager._working_dir(project)

    assert paths[0].name == "docker-compose.yml"
    assert working_dir.name == "legacy"


@pytest.mark.asyncio
async def test_create_project_auto_deploy(compose_manager, tmp_path):
    """创建项目后自动执行 docker compose up -d 并同步状态。"""
    compose_manager.workspace = tmp_path

    db = AsyncMock()
    db.add = MagicMock()

    with patch.object(compose_manager, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
        with patch.object(
            compose_manager, "sync_stack_status", new_callable=AsyncMock
        ) as mock_sync:
            mock_stack = MagicMock()
            mock_stack.service_count = 1
            mock_stack.running_count = 1
            mock_sync.return_value = mock_stack

            project = await compose_manager.create_project(
                db,
                project_name="test-stack",
                content="services:\n  web:\n    image: nginx:latest\n",
                user_id=1,
                description="test",
            )

    assert project.project_name == "test-stack"
    assert project.description == "test"

    assert db.add.call_count == 2
    version_args = db.add.call_args_list[1][0]
    assert isinstance(version_args[0], DockerComposeVersion)
    assert version_args[0].version_number == 1
    assert version_args[0].is_current is True

    mock_run.assert_awaited_once()
    args = mock_run.call_args[0]
    assert args[1:] == ("up", "-d")
    mock_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_project_deploy_fails_still_saved(compose_manager, tmp_path):
    """部署失败时项目记录和版本仍然保留。"""
    compose_manager.workspace = tmp_path

    db = AsyncMock()
    db.add = MagicMock()

    with patch.object(compose_manager, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {
            "returncode": 1,
            "stdout": "",
            "stderr": "no such image",
        }

        with pytest.raises(RuntimeError, match="创建后部署失败"):
            await compose_manager.create_project(
                db,
                project_name="fail-stack",
                content="services:\n  web:\n    image: nonexistent:latest\n",
            )

    assert db.add.call_count == 2
    version_args = db.add.call_args_list[1][0]
    assert isinstance(version_args[0], DockerComposeVersion)
    assert version_args[0].version_number == 1
    assert (tmp_path / "fail-stack" / "docker-compose.yml").exists()


@pytest.mark.asyncio
async def test_edit_and_deploy_creates_version(compose_manager, tmp_path):
    """编辑项目时生成新版本并自动部署。"""
    compose_manager.workspace = tmp_path

    project = DockerComposeProject(
        id=1,
        project_name="edit-stack",
        description="old",
        config_files='["' + str(tmp_path / "edit-stack" / "docker-compose.yml") + '"]',
        working_dir=str(tmp_path / "edit-stack"),
    )
    project.versions = []

    db = AsyncMock()
    db.add = MagicMock()

    # 模拟查询最大版本号，update 返回空结果即可
    mock_max_result = MagicMock()
    mock_max_result.scalar.return_value = 3
    mock_update_result = MagicMock()
    db.execute.side_effect = [mock_max_result, mock_update_result]

    with patch.object(compose_manager, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
        with patch.object(
            compose_manager, "sync_stack_status", new_callable=AsyncMock
        ) as mock_sync:
            mock_stack = MagicMock()
            mock_stack.service_count = 1
            mock_stack.running_count = 1
            mock_sync.return_value = mock_stack

            version, result = await compose_manager.edit_and_deploy(
                db,
                project,
                content="services:\n  web:\n    image: nginx:alpine\n",
                user_id=1,
                comment="升级镜像",
                description="new description",
            )

    assert version.version_number == 4
    assert version.comment == "升级镜像"
    assert version.is_current is True
    assert project.description == "new description"
    assert db.add.call_count == 1
    version_args = db.add.call_args_list[0][0]
    assert isinstance(version_args[0], DockerComposeVersion)
    mock_run.assert_awaited_once()
    args = mock_run.call_args[0]
    assert args[1:] == ("up", "-d")
    mock_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_edit_and_deploy_invalid_yaml(compose_manager, tmp_path):
    """YAML 非法时不创建版本也不部署。"""
    compose_manager.workspace = tmp_path

    project = DockerComposeProject(
        id=1,
        project_name="edit-stack",
        description=None,
        config_files=None,
        working_dir=None,
    )
    project.versions = []

    db = AsyncMock()
    db.add = MagicMock()

    with pytest.raises(ValueError, match="YAML"):
        await compose_manager.edit_and_deploy(
            db,
            project,
            content="services: [\n",
        )

    db.add.assert_not_called()
    db.commit.assert_not_awaited()
