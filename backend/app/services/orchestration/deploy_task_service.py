"""部署任务管理服务。

为应用商店部署和 Compose 部署提供统一的后台任务管理、
进度状态维护与 SSE 推送能力。
"""

import logging
import uuid

from app.services.orchestration.credentials import SENSITIVE_KEY_PATTERN
from app.core.task_manager import BaseTaskManager

logger = logging.getLogger(__name__)

# meta 中需要脱敏的敏感字段名（密码/密钥/令牌类）
_SENSITIVE_KEY_PATTERN = SENSITIVE_KEY_PATTERN
# meta 中完全不对外推送的字段（可能包含明文密码的渲染结果等）
_META_EXCLUDED_KEYS = frozenset({"rendered_yaml"})
_MASKED_VALUE = "***"


def sanitize_meta(meta: dict | None) -> dict | None:
    """对任务 meta 做脱敏处理，用于 SSE 事件对外推送。

    移除可能包含明文敏感信息的字段（如 rendered_yaml），
    并对 password/secret/token/key 类字段打码。
    """
    if meta is None:
        return None
    if not isinstance(meta, dict):
        return meta
    result = {}
    for key, value in meta.items():
        key_str = str(key)
        if key_str in _META_EXCLUDED_KEYS:
            continue
        if _SENSITIVE_KEY_PATTERN.search(key_str):
            result[key] = _MASKED_VALUE
        else:
            result[key] = value
    return result


class DeployTaskManager(BaseTaskManager):
    """部署任务管理器。

    管理后台部署任务的进度状态，支持 SSE 推送。
    """

    _active_status = "deploying"
    _timeout_error = "部署超时，请检查网络或 Compose 配置"

    def __init__(
        self,
        max_tasks: int = 50,
        ttl_seconds: int = 3600,
        max_concurrent: int = 3,
        task_timeout_seconds: int = 1800,
        max_history_size: int = 200,
    ):
        super().__init__(
            max_tasks=max_tasks,
            ttl_seconds=ttl_seconds,
            max_concurrent=max_concurrent,
            task_timeout_seconds=task_timeout_seconds,
        )
        self._max_history_size = max_history_size

    def _concurrency_limit_error(self) -> str:
        return (
            f"并发部署任务数已达上限（{self._max_concurrent}个），"
            f"请等待现有任务完成后再试"
        )

    def _new_progress(self, stage: str, percentage: int, message: str, detail: str | None = None) -> dict:
        """构造新的进度字典。"""
        return {
            "stage": stage,
            "percentage": max(0, min(100, percentage)),
            "message": message,
            "detail": detail,
        }

    def _build_notify(self, task: dict, **extra) -> dict:
        """构造对外推送的通知，meta 统一脱敏。"""
        notify = task["progress"].copy()
        notify["_task_status"] = task["status"]
        notify["_meta"] = sanitize_meta(task.get("meta"))
        notify.update(extra)
        return notify

    def create_task(
        self,
        task_type: str,
        instance_id: int | None = None,
        project_id: int | None = None,
        action: str | None = None,
        meta: dict | None = None,
    ) -> str:
        """创建新部署任务并返回 task_id。"""
        task_id = str(uuid.uuid4())
        now = self._now()
        # 并发上限检查与任务插入在同一个锁临界区内完成，消除 TOCTOU 竞态
        with self._lock:
            self._check_concurrency_limit()
            self._cleanup_expired()
            self._tasks[task_id] = {
                "task_id": task_id,
                "type": task_type,
                "status": "deploying",
                "stage": "preparing",
                "progress": self._new_progress("preparing", 0, "准备中"),
                "error": None,
                "instance_id": instance_id,
                "project_id": project_id,
                "action": action,
                "meta": meta or {},
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
            }
            self._listeners[task_id] = []
            self._append_history(task_id, self._build_notify(self._tasks[task_id]))
        return task_id

    def _append_history(self, task_id: str, notify: dict):
        """追加进度快照到任务历史，便于 SSE 重连后回放。"""
        if task_id not in self._tasks:
            return
        history = self._tasks[task_id].setdefault("progress_history", [])
        history.append(notify)
        if len(history) > self._max_history_size:
            history[:] = history[-self._max_history_size :]

    def update_progress(
        self,
        task_id: str,
        stage: str,
        percentage: int,
        message: str,
        detail: str | None = None,
    ):
        """更新任务进度并通知所有监听器。"""
        progress = self._new_progress(stage, percentage, message, detail)
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["progress"] = progress
            self._tasks[task_id]["stage"] = stage
            self._tasks[task_id]["updated_at"] = self._now()
            notify = self._build_notify(self._tasks[task_id])
            self._append_history(task_id, notify)
            self._notify_listeners(task_id, notify)

    def complete_task(self, task_id: str):
        """标记任务为已完成。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            task = self._tasks[task_id]
            task["status"] = "completed"
            task["stage"] = "completed"
            task["completed_at"] = self._now()
            task["updated_at"] = self._now()
            task["progress"] = self._new_progress("completed", 100, "部署完成")
            notify = self._build_notify(task)
            self._append_history(task_id, notify)
            self._notify_listeners(task_id, notify)

    def fail_task(self, task_id: str, error: str):
        """标记任务为失败。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            task = self._tasks[task_id]
            task["status"] = "failed"
            task["stage"] = "failed"
            task["error"] = error
            task["completed_at"] = self._now()
            task["updated_at"] = self._now()
            progress = task["progress"]
            progress["stage"] = "failed"
            progress["message"] = f"部署失败: {error}"
            notify = self._build_notify(task, _error=error)
            self._append_history(task_id, notify)
            self._notify_listeners(task_id, notify)

    def _on_timeout(self, task: dict):
        """部署任务超时：更新进度阶段并推送脱敏后的失败通知。"""
        task["stage"] = "failed"
        progress = task["progress"]
        progress["stage"] = "failed"
        progress["message"] = task["error"]
        notify = self._build_notify(task, _error=task["error"])
        self._append_history(task["task_id"], notify)
        self._notify_listeners(task["task_id"], notify)

    def get_task_history(self, task_id: str) -> list[dict]:
        """获取任务进度历史快照，用于 SSE 连接时回放。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return []
            self._check_task_timeout(task)
            return [entry.copy() for entry in task.get("progress_history", [])]


# 全局单例，供其他模块直接导入使用
deploy_task_manager = DeployTaskManager()
