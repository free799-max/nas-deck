"""后台任务管理器公共基类。

抽取镜像拉取与部署任务管理器中重复的锁保护、SSE 监听器、
TTL 清理与超时检查逻辑，子类只需定义运行中状态、超时处理
与各自的任务生命周期方法。
"""

import logging
import queue
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseTaskManager:
    """任务管理公共基类：并发上限、监听器、TTL 清理与超时检查。"""

    # 运行中状态标识，由子类定义（如 "pulling" / "deploying"）
    _active_status: str = ""
    # 超时后的错误消息，由子类定义
    _timeout_error: str = "任务超时"

    def __init__(
        self,
        max_tasks: int = 50,
        ttl_seconds: int = 300,
        max_concurrent: int = 3,
        task_timeout_seconds: int = 600,
    ):
        self._tasks: dict[str, dict] = {}
        self._listeners: dict[str, list[queue.Queue]] = {}
        self._lock = threading.Lock()
        self._max_tasks = max_tasks
        self._ttl_seconds = ttl_seconds
        self._max_concurrent = max_concurrent
        self._task_timeout_seconds = task_timeout_seconds

    @staticmethod
    def _now() -> str:
        """返回当前本地时间的 ISO 字符串。"""
        return datetime.now().isoformat()

    def _concurrency_limit_error(self) -> str:
        """并发上限错误消息，由子类定义。"""
        raise NotImplementedError

    def _check_concurrency_limit(self):
        """检查并发上限，需在持有锁的临界区内调用。"""
        running = sum(
            1 for t in self._tasks.values() if t.get("status") == self._active_status
        )
        if running >= self._max_concurrent:
            raise RuntimeError(self._concurrency_limit_error())

    def _notify_listeners(self, task_id: str, message: dict):
        """向任务的所有 SSE 监听器队列推送消息（队列满时丢弃）。"""
        for q in self._listeners.get(task_id, []):
            try:
                q.put_nowait(message)
            except queue.Full:
                pass

    def _on_timeout(self, task: dict):
        """任务超时后的子类钩子：构造并推送超时通知。"""
        raise NotImplementedError

    def _check_task_timeout(self, task: dict) -> bool:
        """检查任务是否已超时，超时时自动标记为失败。"""
        if task.get("status") != self._active_status:
            return False
        if task.get("_timeout_notified"):
            return True
        updated_at = task.get("updated_at")
        if not updated_at:
            return False
        try:
            updated_dt = datetime.fromisoformat(updated_at)
        except (ValueError, TypeError):
            return False
        if (datetime.now() - updated_dt).total_seconds() <= self._task_timeout_seconds:
            return False

        task["status"] = "failed"
        task["error"] = self._timeout_error
        task["completed_at"] = self._now()
        task["updated_at"] = self._now()
        task["_timeout_notified"] = True
        self._on_timeout(task)
        return True

    def get_task(self, task_id: str) -> dict | None:
        """获取任务状态。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                self._check_task_timeout(task)
            return task

    def has_active_task(
        self,
        *,
        instance_id: int | None = None,
        project_id: int | None = None,
    ) -> bool:
        """是否存在指定实例/项目的进行中任务。"""
        with self._lock:
            for task in self._tasks.values():
                if task.get("status") != self._active_status:
                    continue
                if instance_id is not None and task.get("instance_id") == instance_id:
                    return True
                if project_id is not None and task.get("project_id") == project_id:
                    return True
            return False

    def register_listener(self, task_id: str) -> queue.Queue:
        """注册 SSE 监听器队列。"""
        q = queue.Queue(maxsize=100)
        with self._lock:
            if task_id in self._listeners:
                self._listeners[task_id].append(q)
        return q

    def unregister_listener(self, task_id: str, q: queue.Queue):
        """注销 SSE 监听器队列。"""
        with self._lock:
            if task_id in self._listeners:
                try:
                    self._listeners[task_id].remove(q)
                except ValueError:
                    pass

    def _cleanup_expired(self):
        """清理过期和超额的任务。"""
        now = datetime.now()
        expired = []
        for tid, task in self._tasks.items():
            completed_at = task.get("completed_at")
            if completed_at:
                try:
                    completed_dt = datetime.fromisoformat(completed_at)
                    if (now - completed_dt).total_seconds() > self._ttl_seconds:
                        expired.append(tid)
                except (ValueError, TypeError):
                    pass
            elif task.get("status") == self._active_status:
                if self._check_task_timeout(task):
                    expired.append(tid)

        for tid in expired:
            self._tasks.pop(tid, None)
            self._listeners.pop(tid, None)

        if len(self._tasks) > self._max_tasks:
            completed_tasks = [
                (tid, t) for tid, t in self._tasks.items() if t.get("completed_at")
            ]
            completed_tasks.sort(key=lambda x: x[1].get("completed_at", ""))
            to_remove = len(self._tasks) - self._max_tasks
            for tid, _ in completed_tasks[:to_remove]:
                self._tasks.pop(tid, None)
                self._listeners.pop(tid, None)
