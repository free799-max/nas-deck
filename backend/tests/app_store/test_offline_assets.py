"""客户端离线资源档案测试。"""

import yaml

from app.services.apps.offline_assets import (
    MOVIEPILOT,
    apply_offline_profile,
    get_profile,
    image_repo,
    profiles_in_compose,
)


def test_image_repo_strips_tag_registry_port_and_digest():
    assert image_repo("jxxghp/moviepilot-v2:latest") == "jxxghp/moviepilot-v2"
    assert image_repo("jxxghp/moviepilot-v2@sha256:abc") == "jxxghp/moviepilot-v2"
    assert image_repo("registry:5000/team/app:1.0") == "registry:5000/team/app"
    assert image_repo("") == ""


def test_profile_lookup():
    assert get_profile("moviepilot") is MOVIEPILOT
    assert get_profile("nginx") is None


def test_profiles_in_compose_only_matches_known_images():
    content = yaml.safe_dump(
        {
            "services": {
                "moviepilot": {"image": "jxxghp/moviepilot-v2:latest"},
                "other": {"image": "nginx:latest"},
            }
        }
    )
    assert profiles_in_compose(content) == [MOVIEPILOT]
    assert profiles_in_compose("services:\n  other:\n    image: nginx\n") == []


def test_apply_profile_pins_image_and_merges_env():
    content = """services:
  moviepilot:
    image: jxxghp/moviepilot-v2:latest
    environment:
      - TZ=Asia/Shanghai
      - MOVIEPILOT_AUTO_UPDATE=release
  other:
    image: nginx:latest
"""
    out = yaml.safe_load(apply_offline_profile(content))
    moviepilot = out["services"]["moviepilot"]
    assert moviepilot["image"] == MOVIEPILOT.pin_image
    env = moviepilot["environment"]
    assert "TZ=Asia/Shanghai" in env
    assert "MOVIEPILOT_AUTO_UPDATE=false" in env
    assert "MOVIEPILOT_AUTO_UPDATE=release" not in env
    assert "CLOAKBROWSER_AUTO_UPDATE=false" in env
    assert out["services"]["other"]["image"] == "nginx:latest"


def test_apply_profile_keeps_dict_env_style():
    content = """services:
  moviepilot:
    image: jxxghp/moviepilot-v2:latest
    environment:
      TZ: Asia/Shanghai
      MOVIEPILOT_AUTO_UPDATE: release
"""
    out = yaml.safe_load(apply_offline_profile(content))
    env = out["services"]["moviepilot"]["environment"]
    assert env == {
        "TZ": "Asia/Shanghai",
        "MOVIEPILOT_AUTO_UPDATE": "false",
        "AUTO_UPDATE_RESOURCE": "false",
        "CLOAKBROWSER_AUTO_UPDATE": "false",
    }


def test_apply_profile_returns_original_when_no_match():
    content = "services:\n  web:\n    image: nginx:latest\n"
    assert apply_offline_profile(content) == content
