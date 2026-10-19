"""后台 asyncio 任务工具。

asyncio.create_task 仅持有弱引用，任务可能被 GC 提前回收；
这里用模块级集合持有强引用，任务完成后通过回调自动移除。
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

# 持有运行中后台任务的强引用
_background_tasks: set[asyncio.Task] = set()


def create_background_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """创建后台任务并持有强引用，完成后自动移除。"""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
