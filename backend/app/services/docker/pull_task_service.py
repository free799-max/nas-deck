"""镜像拉取任务管理服务。"""

import logging
import uuid

from app.services.task_manager_base import BaseTaskManager

logger = logging.getLogger(__name__)


class ImagePullTaskManager(BaseTaskManager):
    """镜像拉取任务管理器。

    管理后台拉取任务的进度状态，支持 SSE 推送和页面切换恢复。
    """

    _active_status = "pulling"
    _timeout_error = "拉取超时，请检查网络或镜像源配置"

    def __init__(
        self,
        max_tasks: int = 50,
        ttl_seconds: int = 300,
        max_concurrent: int = 3,
        task_timeout_seconds: int = 600,
    ):
        super().__init__(
            max_tasks=max_tasks,
            ttl_seconds=ttl_seconds,
            max_concurrent=max_concurrent,
            task_timeout_seconds=task_timeout_seconds,
        )

    def _concurrency_limit_error(self) -> str:
        return (
            f"并发拉取任务数已达上限（{self._max_concurrent}个），"
            f"请等待现有任务完成后再试"
        )

    def get_running_count(self) -> int:
        """获取当前正在运行的任务数。"""
        with self._lock:
            return sum(
                1 for t in self._tasks.values() if t.get("status") == self._active_status
            )

    def can_start_new_task(self) -> bool:
        """检查是否可以启动新任务。"""
        with self._lock:
            running = sum(
                1 for t in self._tasks.values() if t.get("status") == self._active_status
            )
            return running < self._max_concurrent

    def create_task(self, image: str) -> str:
        """创建新任务并返回 task_id。"""
        task_id = str(uuid.uuid4())
        # 并发上限检查与任务插入在同一个锁临界区内完成，消除 TOCTOU 竞态
        with self._lock:
            self._check_concurrency_limit()
            self._cleanup_expired()
            now = self._now()
            self._tasks[task_id] = {
                "task_id": task_id,
                "image": image,
                "status": "pulling",
                "progress": {
                    "total_layers": 0,
                    "completed_layers": 0,
                    "current_layer": "",
                    "percentage": 0,
                    "status": "准备拉取",
                    "speed": 0,
                    "total_size": 0,
                    "downloaded_size": 0,
                    "size_text": "--",
                    "layers": [],
                },
                "error": None,
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
            }
            self._listeners[task_id] = []
        return task_id

    def update_progress(self, task_id: str, progress: dict):
        """更新任务进度并通知所有监听器。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["progress"] = progress
            self._tasks[task_id]["updated_at"] = self._now()
            self._notify_listeners(task_id, progress)

    def complete_task(self, task_id: str):
        """标记任务为已完成。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            task = self._tasks[task_id]
            task["status"] = "completed"
            progress = task["progress"]
            progress["percentage"] = 100
            progress["status"] = "拉取完成"
            progress["speed"] = 0
            layers = progress.get("layers", [])
            for layer in layers:
                layer["status"] = "Pull complete"
                layer["status_text"] = "已完成"
                layer["percentage"] = 100
                layer["speed"] = 0
            progress["completed_layers"] = len(layers)
            progress["total_layers"] = len(layers)
            progress["size_text"] = "--"
            task["completed_at"] = self._now()
            task["updated_at"] = self._now()
            _notify_progress = task["progress"].copy()
            _notify_progress["_task_status"] = "completed"
            self._notify_listeners(task_id, _notify_progress)

    def fail_task(self, task_id: str, error: str):
        """标记任务为失败。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            task = self._tasks[task_id]
            task["status"] = "failed"
            task["error"] = error
            task["completed_at"] = self._now()
            task["updated_at"] = self._now()
            _notify_progress = task["progress"].copy()
            _notify_progress["_task_status"] = "failed"
            _notify_progress["_error"] = error
            self._notify_listeners(task_id, _notify_progress)

    def _on_timeout(self, task: dict):
        """拉取任务超时：向监听器推送当前进度快照。"""
        self._notify_listeners(task["task_id"], task["progress"])


# 全局单例，供其他模块直接导入使用
task_manager = ImagePullTaskManager()
