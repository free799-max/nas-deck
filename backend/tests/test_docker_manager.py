import pytest
from unittest.mock import MagicMock, patch

from app.core.docker_manager import DockerManager


@pytest.fixture
def mock_docker_client():
    client = MagicMock()
    client.containers = MagicMock()
    client.ping = MagicMock(return_value=True)
    return client


def test_docker_manager_init():
    manager = DockerManager()
    assert manager is not None


@patch("app.core.docker_manager.docker")
def test_list_containers(mock_docker_module):
    mock_container = MagicMock()
    mock_container.id = "abc123def456"
    mock_container.name = "jellyfin"
    mock_container.status = "running"
    mock_container.attrs = {"State": {"Health": {"Status": "healthy"}}}
    mock_container.image.tags = ["jellyfin:latest"]

    mock_client = MagicMock()
    mock_client.containers.list.return_value = [mock_container]
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    containers = manager.list_containers()
    assert len(containers) == 1
    assert containers[0]["name"] == "jellyfin"
    assert containers[0]["status"] == "running"


@patch("app.core.docker_manager.docker")
def test_container_action_stop(mock_docker_module):
    mock_container = MagicMock()
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    manager.container_action("abc123", "stop")
    mock_container.stop.assert_called_once()


@patch("app.core.docker_manager.docker")
def test_container_action_restart(mock_docker_module):
    mock_container = MagicMock()
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    manager.container_action("abc123", "restart")
    mock_container.restart.assert_called_once()
