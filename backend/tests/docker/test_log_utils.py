"""compose 输出/日志处理工具函数测试。"""

from app.services.compose.log_utils import (
    detect_stage,
    is_progress_line,
    strip_ansi,
    summarize_compose_error,
)


def test_strip_ansi_removes_escape_sequences():
    assert strip_ansi("\x1b[32mok\x1b[0m") == "ok"


def test_is_progress_line_matches_layer_progress():
    assert is_progress_line("ec32d732991c Downloading [==>    ] 29.36MB/530.9MB")
    assert is_progress_line(" ec32d732991c Extracting [==>  ]  4.19MB/37.67MB")
    assert is_progress_line("1940b7280541 Pulling fs layer")
    assert is_progress_line("1940b7280541 Waiting")
    assert not is_progress_line("ec32d732991c Download complete")
    assert not is_progress_line(" cloudreve Pulling")
    assert not is_progress_line("Error response from daemon: not found")


def test_summarize_compose_error_filters_progress_lines():
    stderr = "\n".join(
        [f"ec32d732991c Downloading [==>]  {i}MB/530.9MB" for i in range(200)]
        + ["Error response from daemon: Get https://registry: i/o timeout"]
    )
    result = summarize_compose_error(stderr)
    assert "Downloading" not in result
    assert "i/o timeout" in result


def test_summarize_compose_error_all_progress_lines_falls_back_to_last():
    stderr = "\n".join(
        f"ec32d732991c Downloading [==>]  {i}MB/530.9MB" for i in range(50)
    )
    result = summarize_compose_error(stderr)
    assert result.startswith("ec32d732991c Downloading")
    assert result.count("\n") == 0


def test_summarize_compose_error_keeps_last_meaningful_lines():
    stderr = "\n".join(f"error line {i}" for i in range(20))
    result = summarize_compose_error(stderr, max_lines=5)
    assert "error line 19" in result
    assert "error line 14" not in result


def test_summarize_compose_error_empty_input():
    assert summarize_compose_error("") == ""


def test_detect_stage_pulling():
    assert detect_stage("ec32d732991c Downloading") == "pulling_images"
    assert detect_stage(" Container cloudreve Started") == "starting_services"
    assert detect_stage("nothing relevant") is None
