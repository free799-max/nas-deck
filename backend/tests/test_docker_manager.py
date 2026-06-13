import pytest
from unittest.mock import MagicMock, patch

from app.core.docker_manager import DockerManager, ImagePullTaskManager


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


@patch("app.core.docker_manager.docker")
@patch("app.core.docker_manager.time")
def test_pull_progress_monotonic_on_new_layer(mock_time, mock_docker_module):
    """新层动态发现时，总进度不应回退。"""

    # 让每次事件间隔 0.5 秒，既触发节流又触发速度计算
    fake_now = [0.0]

    def _next_time():
        fake_now[0] += 0.5
        return fake_now[0]

    mock_time.time.side_effect = _next_time

    events = [
        # 8 层均下载到 80%
        *[
            {
                "id": f"layer{i}",
                "status": "Downloading",
                "progressDetail": {"current": 80, "total": 100},
            }
            for i in range(8)
        ],
        # 第 9 层先被发现
        {"id": "layer8", "status": "Pulling fs layer", "progressDetail": {}},
        # 第 9 层开始下载，大小 100，当前 0
        {
            "id": "layer8",
            "status": "Downloading",
            "progressDetail": {"current": 0, "total": 100},
        },
    ]

    mock_client = MagicMock()
    mock_client.api.pull.return_value = iter(events)
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    task_manager = ImagePullTaskManager()
    task_id = task_manager.create_task("test:latest")

    recorded = []
    original_update = task_manager.update_progress

    def _update_progress(tid, progress):
        recorded.append(progress["percentage"])
        original_update(tid, progress)

    task_manager.update_progress = _update_progress

    manager.pull_image_async("test:latest", task_id, task_manager)

    # 验证无回退
    for i in range(1, len(recorded)):
        assert recorded[i] >= recorded[i - 1], (
            f"进度从 {recorded[i - 1]}% 回退到 {recorded[i]}%"
        )

    # 最终完成 100%
    task = task_manager.get_task(task_id)
    assert task["status"] == "completed"
    assert task["progress"]["percentage"] == 100


@patch("app.core.docker_manager.docker")
@patch("app.core.docker_manager.time")
def test_pull_progress_byte_weighted(mock_time, mock_docker_module):
    """总进度应按字节加权，大层主导进度而不是简单按层数平均。"""

    fake_now = [0.0]

    def _next_time():
        fake_now[0] += 0.5
        return fake_now[0]

    mock_time.time.side_effect = _next_time

    gb = 1024 * 1024 * 1024
    mb = 1024 * 1024

    events = [
        # 大层 1GB，已下载 800MB
        {
            "id": "big",
            "status": "Downloading",
            "progressDetail": {"current": 800 * mb, "total": 1 * gb},
        },
        # 小层 100MB，尚未开始
        {
            "id": "small",
            "status": "Downloading",
            "progressDetail": {"current": 0, "total": 100 * mb},
        },
    ]

    mock_client = MagicMock()
    mock_client.api.pull.return_value = iter(events)
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    task_manager = ImagePullTaskManager()
    task_id = task_manager.create_task("test:latest")

    last_percentage = [0]

    def _update_progress(tid, progress):
        last_percentage[0] = progress["percentage"]

    task_manager.update_progress = _update_progress

    manager.pull_image_async("test:latest", task_id, task_manager)

    # 层平均 = (80 + 0) / 2 = 40%
    # 字节加权 = 800MB / 1100MB ≈ 72%
    # 取 max 后应接近字节加权
    assert last_percentage[0] >= 65, (
        f"字节加权进度应接近 72%，实际 {last_percentage[0]}%"
    )
    assert last_percentage[0] <= 80


@patch("app.core.docker_manager.docker")
@patch("app.core.docker_manager.time")
def test_pull_progress_completes_at_100(mock_time, mock_docker_module):
    """拉取流结束后，任务应标记为完成并置进度为 100%。"""

    fake_now = [0.0]

    def _next_time():
        fake_now[0] += 0.5
        return fake_now[0]

    mock_time.time.side_effect = _next_time

    events = [
        {
            "id": "layer1",
            "status": "Pull complete",
            "progressDetail": {"current": 100, "total": 100},
        },
    ]

    mock_client = MagicMock()
    mock_client.api.pull.return_value = iter(events)
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    task_manager = ImagePullTaskManager()
    task_id = task_manager.create_task("test:latest")

    manager.pull_image_async("test:latest", task_id, task_manager)

    task = task_manager.get_task(task_id)
    assert task["status"] == "completed"
    assert task["progress"]["percentage"] == 100
    assert task["progress"]["status"] == "拉取完成"


@patch("app.core.docker_manager.docker")
@patch("app.core.docker_manager.time")
def test_pull_progress_all_completed_with_zero_byte_data(mock_time, mock_docker_module):
    """所有层已完成但无字节信息时，进度应基于层平均到达 99%（完成前置 100）。"""

    fake_now = [0.0]

    def _next_time():
        fake_now[0] += 0.5
        return fake_now[0]

    mock_time.time.side_effect = _next_time

    events = [
        # 两层都已完成，但 Docker 没有给出 progressDetail
        {"id": "layer1", "status": "Already exists", "progressDetail": {}},
        {"id": "layer2", "status": "Download complete", "progressDetail": {}},
    ]

    mock_client = MagicMock()
    mock_client.api.pull.return_value = iter(events)
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    task_manager = ImagePullTaskManager()
    task_id = task_manager.create_task("test:latest")

    recorded = []

    def _update_progress(tid, progress):
        recorded.append(progress.copy())

    task_manager.update_progress = _update_progress

    manager.pull_image_async("test:latest", task_id, task_manager)

    # 层平均 100%， capped 到 99%
    assert recorded[-1]["percentage"] == 99
    assert recorded[-1]["completed_layers"] == 2
    assert recorded[-1]["total_layers"] == 2

    task = task_manager.get_task(task_id)
    assert task["status"] == "completed"
    assert task["progress"]["percentage"] == 100


@patch("app.core.docker_manager.docker")
def test_prune_unused_images_counts_tags_not_layers(mock_docker_module):
    """清理未使用镜像时，deleted 应只统计镜像标签，不把层摘要计入镜像数。"""

    mock_client = MagicMock()
    mock_client.images.prune.return_value = {
        "ImagesDeleted": [
            {"Untagged": "nginx:latest"},
            {"Untagged": "redis:latest"},
            {"Deleted": "sha256:abc123"},
            {"Deleted": "sha256:def456"},
            {"Deleted": "sha256:ghi789"},
        ],
        "SpaceReclaimed": 161270000,
    }
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    result = manager.prune_unused_images()

    assert result["deleted"] == ["nginx:latest", "redis:latest"]
    assert result["space_reclaimed"] == 161270000
    # 只应返回 2 个镜像标签，而不是 5 个条目
    assert len(result["deleted"]) == 2


@patch("app.core.docker_manager.docker")
@patch("app.core.docker_manager.time")
def test_pull_progress_counts_100_percent_as_completed(mock_time, mock_docker_module):
    """层百分比达到 100 时，即使状态尚未变为 Pull complete，也应计入已完成层数。"""

    fake_now = [0.0]

    def _next_time():
        fake_now[0] += 0.5
        return fake_now[0]

    mock_time.time.side_effect = _next_time

    events = [
        # 状态仍是 Downloading，但 current == total，百分比 100
        {
            "id": "layer1",
            "status": "Downloading",
            "progressDetail": {"current": 100, "total": 100},
        },
        # 正常 Pull complete
        {"id": "layer2", "status": "Pull complete", "progressDetail": {}},
    ]

    mock_client = MagicMock()
    mock_client.api.pull.return_value = iter(events)
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    task_manager = ImagePullTaskManager()
    task_id = task_manager.create_task("test:latest")

    recorded = []

    def _update_progress(tid, progress):
        recorded.append(progress.copy())

    task_manager.update_progress = _update_progress

    manager.pull_image_async("test:latest", task_id, task_manager)

    # 两层都应计入已完成
    assert recorded[-1]["completed_layers"] == 2
    assert recorded[-1]["total_layers"] == 2


@patch("app.core.docker_manager.docker")
@patch("app.core.docker_manager.time")
def test_complete_task_syncs_layer_counts(mock_time, mock_docker_module):
    """拉取完成时，completed_layers 和 total_layers 应与实际层数一致。"""

    fake_now = [0.0]

    def _next_time():
        fake_now[0] += 0.5
        return fake_now[0]

    mock_time.time.side_effect = _next_time

    events = [
        {"id": "layer1", "status": "Pull complete", "progressDetail": {}},
        {"id": "layer2", "status": "Downloading", "progressDetail": {"current": 50, "total": 100}},
    ]

    mock_client = MagicMock()
    mock_client.api.pull.return_value = iter(events)
    mock_docker_module.from_env.return_value = mock_client

    manager = DockerManager()
    task_manager = ImagePullTaskManager()
    task_id = task_manager.create_task("test:latest")

    manager.pull_image_async("test:latest", task_id, task_manager)

    task = task_manager.get_task(task_id)
    assert task["status"] == "completed"
    assert task["progress"]["percentage"] == 100
    # 完成时两层都应算已完成
    assert task["progress"]["completed_layers"] == 2
    assert task["progress"]["total_layers"] == 2
