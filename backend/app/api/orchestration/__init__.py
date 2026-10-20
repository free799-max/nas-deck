"""应用编排 API 包。

集中导出编排相关路由：
- orchestrations_router: 编排模板浏览、部署、实例管理（/api/orchestrations/*）
- deploy_tasks_router: 部署任务进度查询与 SSE 事件流
"""

from app.api.orchestration.orchestrations import router as orchestrations_router
from app.api.orchestration.deploy_tasks import router as deploy_tasks_router

__all__ = ["orchestrations_router", "deploy_tasks_router"]
