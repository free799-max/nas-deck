"""应用商店服务端口冲突检测单元测试。"""

from unittest.mock import patch

import pytest

from app.core.exceptions import APIException
from app.services.app_store.app_service import (
    _extract_app_ports,
    _get_used_ports,
    _parse_proc_net_tcp,
)


class TestExtractAppPorts:
    """测试单端口字段提取。"""

    def test_extract_integer_port_fields(self):
        """提取类型为 integer 且命名包含 port 的字段。"""
        schema = {
            "properties": {
                "moviepilot_port": {"type": "integer"},
                "api_port": {"type": "integer"},
                "ports": {"type": "array"},
                "name": {"type": "string"},
            }
        }
        assert sorted(_extract_app_ports(schema)) == [
            "api_port",
            "moviepilot_port",
        ]

    def test_return_empty_when_no_port_fields(self):
        """没有相关字段时返回空列表。"""
        assert _extract_app_ports({}) == []
        assert _extract_app_ports({"properties": {"name": {"type": "string"}}}) == []


class TestParseProcNetTcp:
    """测试 /proc/net/tcp 监听端口解析。"""

    def test_parse_listening_ports(self, tmp_path):
        """正确解析 LISTEN 状态的本地端口。"""
        proc_file = tmp_path / "tcp"
        proc_file.write_text(
            "  sl  local_address rem_address   st tx_queue:rx_queue tr:tm when retrnsmt   uid  timeout inode\n"
            "   0: 00000000:0BB8 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 12345 1 0000000000000000 100 0 0 10 0\n"
            "   1: 00000000:0BB9 00000000:0000 01 00000000:00000000 00:00000000 00000000     0        0 12346 1 0000000000000000 100 0 0 10 0\n"
            "   2: 0100007F:0BBA 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 12347 1 0000000000000000 100 0 0 10 0\n"
        )
        # 0BB8=3000, 0BBA=3002，01 状态应被忽略
        assert _parse_proc_net_tcp(str(proc_file)) == {3000, 3002}

    def test_handle_missing_file(self):
        """文件不存在时返回空集合。"""
        assert _parse_proc_net_tcp("/nonexistent/path") == set()


class TestGetUsedPorts:
    """测试占用端口集合合并。"""

    def test_merges_docker_and_proc_ports(self):
        """合并 Docker 容器映射端口与 /proc/net/tcp 监听端口。"""
        fake_container = {
            "HostConfig": {
                "PortBindings": {
                    "3000/tcp": [{"HostPort": "3000"}],
                    "3001/tcp": [{"HostPort": "3001"}],
                }
            }
        }

        with patch("docker.from_env") as mock_docker:
            mock_client = mock_docker.return_value
            mock_client.containers.list.return_value = [
                type("Container", (), {"attrs": fake_container})()
            ]

            with patch(
                "app.services.app_store.app_service._parse_proc_net_tcp"
            ) as mock_parse:
                mock_parse.side_effect = lambda path: {3002} if "tcp6" in path else {3003}
                used = _get_used_ports()

        assert used == {3000, 3001, 3002, 3003}

    def test_skips_docker_when_unavailable(self):
        """Docker 不可用时仍能从 /proc/net/tcp 读取端口。"""
        with patch("docker.from_env", side_effect=Exception("no docker")):
            with patch(
                "app.services.app_store.app_service._parse_proc_net_tcp"
            ) as mock_parse:
                mock_parse.side_effect = lambda path: {8080} if "tcp6" in path else {80}
                used = _get_used_ports()

        assert used == {80, 8080}


class TestValidateAndPreparePorts:
    """测试 _validate_and_prepare 中的端口预检。"""

    @pytest.fixture
    def app_service(self):
        from app.services.app_store.app_service import AppService

        return AppService()

    @pytest.fixture
    def array_port_schema_app(self):
        return type(
            "App",
            (),
            {
                "config_schema": {
                    "type": "object",
                    "properties": {
                        "ports": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "local_port": {"type": "integer"},
                                    "container_port": {"type": "integer"},
                                    "protocol": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                "yaml_template": "services:\n  app:\n    image: test",
            },
        )()

    @pytest.mark.asyncio
    async def test_detects_array_port_conflict(self, app_service, array_port_schema_app):
        """检测到 ports 数组中的 local_port 冲突时抛 409。"""
        with patch(
            "app.services.app_store.app_service._get_used_ports", return_value={3000}
        ):
            with pytest.raises(APIException) as exc_info:
                await app_service._validate_and_prepare(
                    db_app=array_port_schema_app,
                    instance_name="test",
                    config={
                        "ports": [
                            {"local_port": 3000, "container_port": 3000},
                            {"local_port": 3001, "container_port": 3001},
                        ]
                    },
                )

        assert exc_info.value.status_code == 409
        assert "3000" in exc_info.value.message
        assert "ports[0].local_port" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_skips_port_check_when_check_ports_false(
        self, app_service, array_port_schema_app
    ):
        """preview 阶段 check_ports=False 时不检测端口冲突。"""
        with patch(
            "app.services.app_store.app_service._get_used_ports",
            return_value={3000},
        ) as mock_get_used_ports:
            result = await app_service._validate_and_prepare(
                db_app=array_port_schema_app,
                instance_name="test",
                config={
                    "ports": [
                        {"local_port": 3000, "container_port": 3000},
                    ]
                },
                check_ports=False,
            )

        assert result == "test"
        mock_get_used_ports.assert_not_called()

    @pytest.mark.asyncio
    async def test_detects_integer_port_conflict(self, app_service):
        """检测到单端口字段冲突时抛 409。"""
        db_app = type(
            "App",
            (),
            {
                "config_schema": {
                    "type": "object",
                    "properties": {
                        "moviepilot_port": {"type": "integer"}
                    },
                },
                "yaml_template": "services:\n  app:\n    image: test",
            },
        )()

        with patch(
            "app.services.app_store.app_service._get_used_ports", return_value={8096}
        ):
            with pytest.raises(APIException) as exc_info:
                await app_service._validate_and_prepare(
                    db_app=db_app,
                    instance_name="test",
                    config={"moviepilot_port": 8096},
                )

        assert exc_info.value.status_code == 409
        assert "8096" in exc_info.value.message
        assert "moviepilot_port" in exc_info.value.message
