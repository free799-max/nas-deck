"""镜像拉取任务管理服务。"""

import logging
import queue
import threading
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class ImagePullTaskManager:
    """镜像拉取任务管理器。

    管理后台拉取任务的进度状态，支持 SSE 推送和页面切换恢复。
    """

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

    def get_running_count(self) -> int:
        """获取当前正在运行的任务数。"""
        with self._lock:
            return sum(
                1 for t in self._tasks.values() if t.get("status") == "pulling"
            )

    def can_start_new_task(self) -> bool:
        """检查是否可以启动新任务。"""
        with self._lock:
            running = sum(
                1 for t in self._tasks.values() if t.get("status") == "pulling"
            )
            return running < self._max_concurrent

    def create_task(self, image: str) -> str:
        """创建新任务并返回 task_id。"""
        with self._lock:
            running = sum(
                1 for t in self._tasks.values() if t.get("status") == "pulling"
            )
            if running >= self._max_concurrent:
                raise RuntimeError(
                    f"并发拉取任务数已达上限（{self._max_concurrent}个），"
                    f"请等待现有任务完成后再试"
                )

        task_id = str(uuid.uuid4())
        with self._lock:
            self._cleanup_expired()
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
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
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
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(progress)
                except queue.Full:
                    pass

    def complete_task(self, task_id: str):
        """标记任务为已完成。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["status"] = "completed"
            progress = self._tasks[task_id]["progress"]
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
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            _notify_progress = self._tasks[task_id]["progress"].copy()
            _notify_progress["_task_status"] = "completed"
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(_notify_progress)
                except queue.Full:
                    pass

    def fail_task(self, task_id: str, error: str):
        """标记任务为失败。"""
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = error
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
            _notify_progress = self._tasks[task_id]["progress"].copy()
            _notify_progress["_task_status"] = "failed"
            _notify_progress["_error"] = error
            for q in self._listeners.get(task_id, []):
                try:
                    q.put_nowait(_notify_progress)
                except queue.Full:
                    pass

    def _check_task_timeout(self, task: dict) -> bool:
        """检查任务是否已超时，超时时自动标记为失败。"""
        if task.get("status") != "pulling":
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
                task["error"] = "拉取超时，请检查网络或镜像源配置"
                task["completed_at"] = datetime.now().isoformat()
                task["updated_at"] = datetime.now().isoformat()
                task["_timeout_notified"] = True
                for q in self._listeners.get(task["task_id"], []):
                    try:
                        q.put_nowait(task["progress"])
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
            elif task.get("status") == "pulling":
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
task_manager = ImagePullTaskManager()
