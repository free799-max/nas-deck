"""编排方案/实例组版本变更事件的写入辅助。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orchestration import OrchestrationUpdateEvent


def add_update_event(
    db: AsyncSession,
    *,
    orchestration_name: str,
    scope: str,
    mode: str,
    status: str,
    group_id: int | None = None,
    from_version: str | None = None,
    to_version: str | None = None,
    detail: dict | None = None,
    message: str | None = None,
) -> OrchestrationUpdateEvent:
    """把一条版本变更事件加入会话（不提交，由调用方统一 commit）。

    scope: template（模板同步）/ instance（实例组部署、重建、升级）
    mode: auto（定时同步）/ manual（用户触发）
    status: applied / failed
    """
    event = OrchestrationUpdateEvent(
        orchestration_name=orchestration_name,
        scope=scope,
        group_id=group_id,
        from_version=from_version,
        to_version=to_version,
        mode=mode,
        status=status,
        detail=detail or {},
        message=message,
    )
    db.add(event)
    return event
