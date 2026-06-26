"""部署任务管理服务。

为应用商店部署和 Compose 部署提供统一的后台任务管理、
进度状态维护与 SSE 推送能力。
"""

import logging
import queue
import threading
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class DeployTaskManager:
    """部署任务管理器。

    管理后台部署任务的进度状态，支持 SSE 推送。
    """

    def __init__(
        self,
        max_tasks: int = 50,
        ttl_seconds: int = 3600,
        max_concurrent: int = 3,
        task_timeout_seconds: int = 1800,
        max_history_size: int = 200,
    ):
        self._tasks: dict[str, dict] = {}
        self._listeners: dict[str, list[queue.Queue]] = {}
        self._lock = threading.Lock()
        self._max_tasks = max_tasks
        self._ttl_seconds = ttl_seconds
        self._max_concurrent = max_concurrent
        self._task_timeout_seconds = task_timeout_seconds
        self._max_history_size = max_history_size

    def _new_progress(self, stage: str, percentage: int, message: str, detail: str | None = None) -> dict:
        """构造新的进度字典。"""
        return {
            "stage": stage,
            "percentage": max(0, min(100, percentage)),
            "message": message,
            "detail": detail,
        }

    def create_task(
        self,
        task_type: str,
        instance_id: int | None = None,
        project_id: int | None = None,
        action: str | None = None,
        meta: dict | None = None,
    ) -> str:
        """创建新部署任务并返回 task_id。"""
        with self._lock:
            running = sum(
                1 for t in self._tasks.values() if t.get("status") == "deploying"
            )
            if running >= self._max_concurrent:
                raise RuntimeError(
                    f"并发部署任务数已达上限（{self._max_concurrent}个），"
                    f"请等待现有任务完成后再试"
                )

        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with self._lock:
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
            _initial_notify = self._tasks[task_id]["progress"].copy()
            _initial_notify["_task_status"] = self._tasks[task_id]["status"]
            _initial_notify["_meta"] = self._tasks[task_id].get("meta")
            self._append_history(task_id, _initial_notify)
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
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            _notify = progress.copy()
            _notify["_task_status"] = self._tasks[task_id]["status"]
            _notify["_meta"] = self._tasks[task_id].get("meta")
            self._append_history(task_id, _notify)
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(_notify)
                except queue.Full:
                    pass

    def complete_task(self, task_id: str):
        """标记任务为已完成。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["status"] = "completed"
            self._tasks[task_id]["stage"] = "completed"
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            progress = self._new_progress("completed", 100, "部署完成")
            self._tasks[task_id]["progress"] = progress
            _notify = progress.copy()
            _notify["_task_status"] = "completed"
            _notify["_meta"] = self._tasks[task_id].get("meta")
            self._append_history(task_id, _notify)
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(_notify)
                except queue.Full:
                    pass

    def fail_task(self, task_id: str, error: str):
        """标记任务为失败。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["stage"] = "failed"
            self._tasks[task_id]["error"] = error
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            progress = self._tasks[task_id]["progress"]
            progress["stage"] = "failed"
            progress["message"] = f"部署失败: {error}"
            _notify = progress.copy()
            _notify["_task_status"] = "failed"
            _notify["_error"] = error
            _notify["_meta"] = self._tasks[task_id].get("meta")
            self._append_history(task_id, _notify)
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(_notify)
                except queue.Full:
                    pass

    def _check_task_timeout(self, task: dict) -> bool:
        """检查任务是否已超时，超时时自动标记为失败。"""
        if task.get("status") != "deploying":
            return False
        if task.get("_timeout_notified"):
            return True
        updated_at = task.get("updated_at")
        if not updated_at:
            return False
        try:
            updated_dt = datetime.fromisoformat(updated_at)
            if (datetime.now() - updated_dt).total_seconds() > self._task_timeout_seconds:
                task["status"] = "failed"
                task["stage"] = "failed"
                task["error"] = "部署超时，请检查网络或 Compose 配置"
                task["completed_at"] = datetime.now().isoformat()
                task["updated_at"] = datetime.now().isoformat()
                task["_timeout_notified"] = True
                progress = task["progress"]
                progress["stage"] = "failed"
                progress["message"] = task["error"]
                _notify = progress.copy()
                _notify["_task_status"] = "failed"
                _notify["_error"] = task["error"]
                _notify["_meta"] = task.get("meta")
                self._append_history(task["task_id"], _notify)
                for q in self._listeners.get(task["task_id"], []):
                    try:
                        q.put_nowait(_notify)
                    except queue.Full:
                        pass
                return True
        except Exception:
            pass
        return False

    def get_task(self, task_id: str) -> dict | None:
        """获取任务状态。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                self._check_task_timeout(task)
            return task

    def get_task_history(self, task_id: str) -> list[dict]:
        """获取任务进度历史快照，用于 SSE 连接时回放。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return []
            self._check_task_timeout(task)
            return [entry.copy() for entry in task.get("progress_history", [])]

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
                except Exception:
                    pass
            elif task.get("status") == "deploying":
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


# 全局单例，供其他模块直接导入使用
deploy_task_manager = DeployTaskManager()
