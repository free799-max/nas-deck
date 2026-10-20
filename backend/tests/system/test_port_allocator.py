"""服务端口分配与 Compose 端口重写单元测试。"""

import pytest
import yaml

from app.services.compose.yaml_utils import rewrite_ports
from app.services.system.port_allocator import (
    _reserved,
    allocate_and_reserve,
    allocate_free_ports,
    get_reserved_ports,
    release_ports,
    reserve_ports,
)


class TestAllocateFreePorts:
    """测试 allocate_free_ports 顺序分配与跳过占用逻辑。"""

    def test_allocates_sequentially_from_start(self):
        """从起始端口开始按顺序分配。"""
        assert allocate_free_ports(set(), 3, 10000) == [10000, 10001, 10002]

    def test_skips_used_ports(self):
        """跳过已占用端口。"""
        used = {10000, 10002}
        assert allocate_free_ports(used, 3, 10000) == [10001, 10003, 10004]

    def test_does_not_mutate_used_set(self):
        """不修改调用方传入的 used 集合。"""
        used = {10000}
        allocate_free_ports(used, 2, 10000)
        assert used == {10000}

    def test_raises_when_exceeding_max_port(self):
        """候选端口超过 65535 时抛异常。"""
        with pytest.raises(ValueError, match="空闲端口"):
            allocate_free_ports(set(), 2, 65535)

    def test_count_zero_returns_empty(self):
        """分配数量为 0 时返回空列表。"""
        assert allocate_free_ports({1, 2, 3}, 0, 10000) == []


class TestRewritePorts:
    """测试 rewrite_ports 对各种 ports 语法形式的重写。"""

    @staticmethod
    def _rewrite(content: str, used=None, start=10000) -> dict:
        result = rewrite_ports(content, used or set(), start)
        return yaml.safe_load(result)

    def test_short_syntax_host_container(self):
        """短语法 "8080:80" 只改宿主端口段。"""
        data = self._rewrite(
            "services:\n  web:\n    image: nginx\n    ports:\n      - \"8080:80\"\n"
        )
        assert data["services"]["web"]["ports"] == ["10000:80"]

    def test_short_syntax_with_ip_prefix(self):
        """带 IP 前缀的 "127.0.0.1:8080:80" 保留 IP，只改宿主端口。"""
        data = self._rewrite(
            "services:\n  web:\n    image: nginx\n"
            "    ports:\n      - \"127.0.0.1:8080:80\"\n"
        )
        assert data["services"]["web"]["ports"] == ["127.0.0.1:10000:80"]

    def test_short_syntax_with_protocol_suffix(self):
        """带协议后缀的 "8080:80/udp" 保留 /udp。"""
        data = self._rewrite(
            "services:\n  web:\n    image: nginx\n"
            "    ports:\n      - \"8080:80/udp\"\n"
        )
        assert data["services"]["web"]["ports"] == ["10000:80/udp"]

    def test_plain_integer_entry(self):
        """纯数字条目（宿主=容器）重写为分配端口。"""
        data = self._rewrite(
            "services:\n  web:\n    image: nginx\n    ports:\n      - 3000\n"
        )
        assert data["services"]["web"]["ports"] == [10000]

    def test_plain_numeric_string_entry(self):
        """纯数字字符串 "3000" 同样重写为分配端口。"""
        data = self._rewrite(
            "services:\n  web:\n    image: nginx\n    ports:\n      - \"3000\"\n"
        )
        assert data["services"]["web"]["ports"] == ["10000"]

    def test_range_entries_untouched(self):
        """含范围 "-" 的条目不改动，也不占用分配序号。"""
        content = (
            "services:\n  web:\n    image: nginx\n    ports:\n"
            "      - \"3000-3010:3000-3010\"\n"
            "      - \"8080:80\"\n"
        )
        result = rewrite_ports(content, set(), 10000)
        data = yaml.safe_load(result)
        assert data["services"]["web"]["ports"] == [
            "3000-3010:3000-3010",
            "10000:80",
        ]

    def test_long_syntax_published(self):
        """长语法 dict 重写 published 字段。"""
        content = (
            "services:\n  web:\n    image: nginx\n    ports:\n"
            "      - target: 80\n        published: 8080\n        protocol: tcp\n"
        )
        data = self._rewrite(content)
        entry = data["services"]["web"]["ports"][0]
        assert entry["published"] == 10000
        assert entry["target"] == 80
        assert entry["protocol"] == "tcp"

    def test_long_syntax_string_published_keeps_type(self):
        """长语法 published 为字符串时保持字符串类型。"""
        content = (
            "services:\n  web:\n    image: nginx\n    ports:\n"
            "      - target: 80\n        published: \"8080\"\n"
        )
        data = self._rewrite(content)
        assert data["services"]["web"]["ports"][0]["published"] == "10000"

    def test_multiple_services_sequential_and_skip_used(self):
        """多服务按顺序分配，跳过已占用端口。"""
        content = (
            "services:\n"
            "  a:\n    image: nginx\n    ports:\n      - \"8080:80\"\n"
            "  b:\n    image: nginx\n    ports:\n      - \"9090:90\"\n"
        )
        data = self._rewrite(content, used={10001})
        assert data["services"]["a"]["ports"] == ["10000:80"]
        assert data["services"]["b"]["ports"] == ["10002:90"]

    def test_skips_non_port_entries(self):
        """非端口映射条目跳过且不占用分配序号。"""
        content = (
            "services:\n  web:\n    image: nginx\n    ports:\n"
            "      - \"not-a-port\"\n      - \"8080:80\"\n"
        )
        data = self._rewrite(content)
        assert data["services"]["web"]["ports"] == ["not-a-port", "10000:80"]

    def test_invalid_yaml_returns_original(self):
        """YAML 解析失败时原样返回。"""
        content = "services: [unclosed"
        assert rewrite_ports(content, set(), 10000) == content

    def test_no_services_returns_original(self):
        """无 services 字段时原样返回。"""
        content = "version: \"3\"\n"
        assert rewrite_ports(content, set(), 10000) == content

    def test_no_ports_returns_original(self):
        """服务没有 ports 时原样返回。"""
        content = "services:\n  web:\n    image: nginx\n"
        assert rewrite_ports(content, set(), 10000) == content

    def test_raises_when_no_free_ports(self):
        """无可用端口时抛 ValueError。"""
        content = (
            "services:\n  web:\n    image: nginx\n    ports:\n      - \"8080:80\"\n"
        )
        with pytest.raises(ValueError, match="空闲端口"):
            rewrite_ports(content, set(), 65536)


class TestPortReservation:
    """端口预留：防止并发部署重复分配同一端口。"""

    def teardown_method(self):
        release_ports(list(_reserved))

    def test_allocate_and_reserve_skips_reserved(self):
        first = allocate_and_reserve(set(), 2, 10000)
        assert first == [10000, 10001]
        # 同起始端口的第二次分配（模拟同批另一个应用）必须跳过已预留端口
        second = allocate_and_reserve(set(), 2, 10000)
        assert second == [10002, 10003]

    def test_allocate_free_ports_also_skips_reserved(self):
        reserve_ports([10000, 10002])
        assert allocate_free_ports(set(), 3, 10000) == [10001, 10003, 10004]

    def test_release_ports_frees_reservation(self):
        reserve_ports([10000])
        release_ports([10000])
        assert allocate_free_ports(set(), 1, 10000) == [10000]

    def test_release_is_idempotent_and_ignores_empty(self):
        release_ports([])
        release_ports(None)
        release_ports([12345])
        assert 12345 not in get_reserved_ports()
