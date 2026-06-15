"""
Docker 容器管理 API 模块

提供 Docker 容器相关的管理接口，包括：
- 查询 Docker 服务是否可用
- 获取容器列表
- 获取单个容器详情
- 对容器执行操作（启动、停止、重启等）
- 获取容器日志

所有端点挂载在 /api/docker 路径下，需要用户已登录。
"""

import asyncio
import json
import threading
import queue
import logging

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIException
import docker

logger = logging.getLogger(__name__)

from app.models.user import User
from app.models.docker import (
    DockerMirrorConfig,
    DockerComposeProject,
    DockerComposeVersion,
    DockerComposeStack,
)
from app.schemas.docker import (
    ContainerInfo, ContainerAction, ContainerActionResponse, ContainerCreateRequest,
    ContainerDetail, ContainerBatchActionRequest,
    ContainerExecRequest, ContainerExecResponse,
    HostInfo,
    ImageInfo, ImageDetail, ImagePruneResult, ImageSearchResult,
    ImagePullRequest, ImageTag, PullTaskResponse, PullTaskStatus,
    RegistryCreate, RegistryUpdate, RegistryOut,
    BatchImageDeleteRequest,
    ComposeProjectCreate, ComposeProjectUpdate, ComposeProjectOut,
    ComposeVersionCreate, ComposeVersionOut,
    ComposeActionRequest, ComposeStackStatusOut,
    ComposeEditRequest,
)
from app.core.security import get_current_user, get_current_user_sse
from app.core.docker_manager import docker_manager, task_manager
from app.core.compose_manager import compose_manager
from app.core.custom_route import CustomAPIRoute
from app.database import get_db, async_session
from app.config import settings

# 创建 Docker 管理路由器，路径前缀为 /api/docker，标签为 docker
router = APIRouter(prefix="/api/docker", tags=["docker"], route_class=CustomAPIRoute)


@router.get("/status")
async def docker_status(current_user: User = Depends(get_current_user)):
    """
    查询 Docker 服务状态

    返回当前系统中 Docker 服务是否可用。

    Args:
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        dict: 包含 available 字段，表示 Docker 是否可用
    """
    return {"available": docker_manager.available}


@router.get("/containers", response_model=list[ContainerInfo])
async def list_containers(current_user: User = Depends(get_current_user)):
    """
    获取所有容器列表

    返回当前 Docker 环境中所有容器的信息列表。

    Args:
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        list[ContainerInfo]: 容器信息列表
    """
    return docker_manager.list_containers()


@router.get("/containers/{container_id}", response_model=ContainerInfo)
async def get_container(container_id: str, current_user: User = Depends(get_current_user)):
    """
    获取单个容器的详细信息

    根据容器 ID 查询并返回该容器的详细信息。

    Args:
        container_id: 容器的 ID 或名称
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        ContainerInfo: 容器详细信息

    Raises:
        APIException: 当容器不存在时返回 404 错误
    """
    # 通过 docker_manager 查询容器
    container = docker_manager.get_container(container_id)
    if not container:
        raise APIException("容器不存在", 404)
    return container


@router.post("/containers/{container_id}/action", response_model=ContainerActionResponse)
async def container_action(
    container_id: str,
    data: ContainerAction,
    current_user: User = Depends(get_current_user),
):
    """
    对容器执行操作

    对指定容器执行操作，如启动（start）、停止（stop）、重启（restart）。
    启动/重启操作会等待容器真正进入 running 状态；若失败则返回具体错误信息。

    Args:
        container_id: 容器的 ID 或名称
        data: 容器操作请求数据，包含要执行的操作类型
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        ContainerActionResponse: 操作后的容器状态和错误信息

    Raises:
        APIException: 当容器不存在时返回 404 错误
        APIException: 当 Docker 不可用时返回 503 错误
        APIException: 当操作执行失败时返回 500 错误
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    try:
        # 执行容器操作（如 start、stop、restart）
        return docker_manager.container_action(container_id, data.action)
    except docker.errors.NotFound:
        # 容器不存在
        raise APIException("容器不存在", 404)
    except ValueError as e:
        # 操作类型不合法
        raise APIException(str(e), 400)
    except RuntimeError as e:
        # Docker 不可用或状态等待失败
        raise APIException(str(e), 500)
    except Exception as e:
        # 其他操作异常
        raise APIException(f"容器操作失败: {e}", 500)


@router.get("/containers/{container_id}/logs")
async def container_logs(
    container_id: str,
    tail: int = 100,
    current_user: User = Depends(get_current_user),
):
    """
    获取容器日志

    获取指定容器的最近日志输出。

    Args:
        container_id: 容器的 ID 或名称
        tail: 返回最后 N 行日志，默认为 100 行
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        dict: 包含 logs 字段，为容器日志内容
    """
    # 获取容器的日志，tail 参数控制返回的行数
    logs = docker_manager.get_container_logs(container_id, tail=tail)
    return {"logs": logs}


@router.post("/containers", response_model=ContainerInfo, status_code=status.HTTP_201_CREATED)
async def create_container(
    data: ContainerCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """创建容器。

    根据请求参数创建 Docker 容器，创建成功后返回容器基本信息。

    Args:
        data: 创建容器请求数据
        current_user: 当前登录用户

    Returns:
        ContainerInfo: 创建后的容器信息

    Raises:
        APIException: 当 Docker 不可用时返回 503
        APIException: 当镜像不存在时返回 404
        APIException: 当创建失败时返回 500
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    try:
        return docker_manager.create_container(data.model_dump())
    except docker.errors.ImageNotFound:
        raise APIException("镜像不存在", 404)
    except docker.errors.APIError as e:
        raise APIException(f"创建容器失败: {e}", 500)
    except Exception as e:
        raise APIException(f"创建容器失败: {e}", 500)


@router.post("/containers/batch-action")
async def batch_container_action(
    data: ContainerBatchActionRequest,
    current_user: User = Depends(get_current_user),
):
    """批量操作容器。

    对多个容器执行启动、停止、重启或删除操作。

    Args:
        data: 批量操作请求数据
        current_user: 当前登录用户

    Returns:
        dict: 包含 succeeded 和 failed 列表的结果

    Raises:
        APIException: 当 Docker 不可用时返回 503
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    try:
        return docker_manager.batch_container_action(data.ids, data.action)
    except ValueError as e:
        raise APIException(str(e), 400)
    except Exception as e:
        raise APIException(f"批量操作失败: {e}", 500)


@router.get("/containers/{container_id}/detail", response_model=ContainerDetail)
async def get_container_detail(
    container_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取容器完整详情。

    Args:
        container_id: 容器 ID 或名称
        current_user: 当前登录用户

    Returns:
        ContainerDetail: 容器详情

    Raises:
        APIException: 当 Docker 不可用时返回 503
        APIException: 当容器不存在时返回 404
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    detail = docker_manager.get_container_detail(container_id)
    if not detail:
        raise APIException("容器不存在", 404)
    return detail


@router.get("/containers/{container_id}/logs/stream")
async def container_logs_stream(
    container_id: str,
    tail: int = 100,
    follow: bool = True,
    timestamps: bool = True,
    current_user: User = Depends(get_current_user_sse),
):
    """流式获取容器日志（SSE）。

    建立 SSE 连接，实时推送容器日志。

    Args:
        container_id: 容器 ID 或名称
        tail: 返回最后 N 行日志，默认 100
        follow: 是否持续跟踪新日志
        timestamps: 是否包含时间戳
        current_user: 当前登录用户

    Returns:
        StreamingResponse: SSE 日志流

    Raises:
        APIException: 当 Docker 不可用时返回 503
        APIException: 当容器不存在时返回 404
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)

    def _stream_to_queue(q: queue.Queue, stop_event: threading.Event):
        """在线程中读取日志并写入队列。"""
        try:
            # 先推送容器元数据，便于前端展示状态
            detail = docker_manager.get_container_status(container_id)
            if detail is None:
                q.put({"error": "容器不存在"})
                return
            q.put(
                {
                    "meta": {
                        "container_id": detail["id"],
                        "name": detail["name"],
                        "status": detail["status"],
                        "state": detail["state"],
                    }
                }
            )

            for line in docker_manager.stream_container_logs(
                container_id,
                tail=tail,
                follow=follow,
                timestamps=timestamps,
            ):
                if stop_event.is_set():
                    break
                q.put({"line": line})
        except docker.errors.NotFound:
            q.put({"error": "容器不存在"})
        except docker.errors.APIError as e:
            message = str(e)
            if "configured logging driver does not support reading" in message:
                q.put({"error": "容器日志驱动不支持读取，请检查容器日志驱动配置"})
            elif "No such container" in message:
                q.put({"error": "容器不存在"})
            else:
                q.put({"error": f"日志流异常: {message}"})
        except Exception as e:
            q.put({"error": f"日志流异常: {e}"})
        finally:
            q.put(None)

    async def event_generator():
        """SSE 事件生成器。"""
        q: queue.Queue = queue.Queue(maxsize=500)
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_stream_to_queue,
            args=(q, stop_event),
            daemon=True,
        )
        thread.start()
        try:
            while True:
                try:
                    item = await asyncio.get_event_loop().run_in_executor(
                        None, q.get, True, 1.0
                    )
                except queue.Empty:
                    continue
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            stop_event.set()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/containers/{container_id}/exec", response_model=ContainerExecResponse)
async def container_exec(
    container_id: str,
    data: ContainerExecRequest,
    current_user: User = Depends(get_current_user),
):
    """在容器内执行命令。

    Args:
        container_id: 容器 ID 或名称
        data: 执行命令请求数据
        current_user: 当前登录用户

    Returns:
        ContainerExecResponse: 命令退出码和输出

    Raises:
        APIException: 当 Docker 不可用时返回 503
        APIException: 当容器不存在时返回 404
        APIException: 当执行失败时返回 500
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    try:
        exit_code, output = docker_manager.exec_container(
            container_id,
            data.command,
            workdir=data.workdir,
            user=data.user,
            environment=[item.model_dump() for item in (data.environment or [])],
        )
        return {"exit_code": exit_code, "output": output}
    except docker.errors.NotFound:
        raise APIException("容器不存在", 404)
    except Exception as e:
        raise APIException(f"执行命令失败: {e}", 500)


@router.websocket("/containers/{container_id}/exec")
async def container_terminal_websocket(
    websocket: WebSocket,
    container_id: str,
    shell: str = "/bin/sh",
    workdir: str | None = None,
    user: str | None = None,
    cols: int = 80,
    rows: int = 24,
):
    """容器交互式终端 WebSocket。

    建立类似 `docker exec -it <container> <shell>` 的伪终端会话，
    前端通过 xterm.js 与本端点双向通信。

    消息协议：
    - 服务端 -> 客户端：普通文本，为容器 stdout/stderr 输出（tty=True 已合并）。
    - 客户端 -> 服务端：
      - 普通文本：作为 stdin 写入容器。
      - JSON {"type": "resize", "cols": 80, "rows": 24}：调整终端尺寸。

    Args:
        websocket: WebSocket 连接对象
        container_id: 容器 ID 或名称
        shell: 要启动的 shell，默认 /bin/sh
        workdir: 工作目录
        user: 执行用户
        cols: 初始终端列数
        rows: 初始终端行数
    """
    # WebSocket 不支持 HTTPBearer 依赖，从 query 参数手动认证
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="缺少认证令牌")
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        sub = payload.get("sub")
        if sub is None:
            raise JWTError
        user_id = int(sub)
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=1008, reason="认证失败")
        return

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        current_user = result.scalar_one_or_none()
    if current_user is None:
        await websocket.close(code=1008, reason="认证失败")
        return

    if not docker_manager.available:
        await websocket.close(code=1011, reason="Docker 不可用")
        return

    try:
        exec_id, exec_socket = docker_manager.exec_container_interactive(
            container_id,
            command=[shell],
            workdir=workdir,
            user=user,
        )
        # 设置初始终端尺寸
        try:
            docker_manager._client.api.exec_resize(exec_id, height=rows, width=cols)
        except Exception:
            pass
    except docker.errors.NotFound:
        await websocket.close(code=1011, reason="容器不存在")
        return
    except Exception as e:
        await websocket.close(code=1011, reason=f"创建 exec 会话失败: {e}")
        return

    await websocket.accept()

    output_queue: queue.Queue = queue.Queue(maxsize=1000)

    def _read_socket():
        """在线程中读取 Docker exec socket 输出。"""
        # Docker SDK 7.x 的 SocketIO.read() 在等待输出时可能超时返回，
        # 导致交互式会话被误关闭。改用底层 socket recv() 阻塞读取。
        try:
            exec_socket._sock.settimeout(None)
        except Exception:
            pass
        try:
            while True:
                try:
                    chunk = exec_socket._sock.recv(4096)
                except Exception:
                    break
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                try:
                    output_queue.put(text, block=False)
                except queue.Full:
                    pass
        finally:
            try:
                output_queue.put(None, block=False)
            except queue.Full:
                pass

    reader_thread = threading.Thread(target=_read_socket, daemon=True)
    reader_thread.start()

    async def _forward_to_container():
        """将前端输入转发到容器 exec socket。"""
        try:
            while True:
                message = await websocket.receive_text()
                # 尝试解析 resize 控制消息
                try:
                    data = json.loads(message)
                    if isinstance(data, dict) and data.get("type") == "resize":
                        new_cols = int(data.get("cols", cols))
                        new_rows = int(data.get("rows", rows))
                        try:
                            docker_manager._client.api.exec_resize(
                                exec_id, height=new_rows, width=new_cols
                            )
                        except Exception:
                            pass
                        continue
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

                # 普通输入写入 socket
                # Docker SDK 7.x 的 exec socket 是只读 SocketIO，
                # 需要通过底层 _sock 发送 stdin。
                await asyncio.get_event_loop().run_in_executor(
                    None, exec_socket._sock.sendall, message.encode("utf-8")
                )
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    async def _forward_to_client():
        """将容器输出转发到前端 WebSocket。"""
        while True:
            try:
                item = await asyncio.get_event_loop().run_in_executor(
                    None, output_queue.get, True, 0.5
                )
            except queue.Empty:
                continue
            if item is None:
                break
            await websocket.send_text(item)

    try:
        await asyncio.gather(_forward_to_container(), _forward_to_client())
    finally:
        try:
            exec_socket.close()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/host/info", response_model=HostInfo)
async def get_host_info(current_user: User = Depends(get_current_user)):
    """获取 Docker 宿主机综合信息。

    返回 Docker 宿主机的主机名、操作系统、架构、内核版本、
    Docker 引擎版本、资源信息、Docker 统计信息和网络列表。
    即使后端部署在 Docker 容器内，返回的也是宿主机的信息。

    Args:
        current_user: 当前登录用户（通过依赖注入获取）

    Returns:
        HostInfo: 宿主机综合信息

    Raises:
        APIException: 当 Docker 服务不可用时返回 503 错误
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    info = docker_manager.get_host_info()
    if not info:
        raise APIException("Docker 不可用", 503)
    return info


# ===================== 镜像管理 =====================

@router.get("/images", response_model=list[ImageInfo])
async def list_images(current_user: User = Depends(get_current_user)):
    """获取本地镜像列表（扁平化，每行对应一个 tag）。

    Args:
        current_user: 当前登录用户

    Returns:
        list[ImageInfo]: 本地镜像列表
    """
    return docker_manager.list_images()


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_image(
    image_id: str,
    force: bool = False,
    current_user: User = Depends(get_current_user),
):
    """删除指定镜像。

    Args:
        image_id: 镜像 ID 或标签
        force: 是否强制删除
        current_user: 当前登录用户

    Raises:
        APIException: 镜像不存在或删除失败
    """
    try:
        docker_manager.remove_image(image_id, force=force)
    except docker.errors.ImageNotFound:
        raise APIException("镜像不存在", 404)
    except docker.errors.APIError as e:
        raise APIException(f"删除镜像失败: {e}", 500)


@router.get("/images/{image_id}/detail", response_model=ImageDetail)
async def get_image_detail(
    image_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取镜像完整元数据。

    Args:
        image_id: 镜像完整 ID（sha256:...）或短 ID。
        current_user: 当前登录用户

    Returns:
        ImageDetail: 镜像元数据

    Raises:
        APIException: 镜像不存在时返回 404
        APIException: Docker 不可用时返回 503
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    detail = docker_manager.get_image_detail(image_id)
    if not detail:
        raise APIException("镜像不存在", 404)
    return detail


@router.post("/images/prune", response_model=ImagePruneResult)
async def prune_images(current_user: User = Depends(get_current_user)):
    """移除所有未使用的镜像。

    移除所有未被容器引用的镜像，包括有标签但无容器使用的镜像。

    Args:
        current_user: 当前登录用户

    Returns:
        ImagePruneResult: 被删除的镜像列表和释放空间

    Raises:
        APIException: Docker 不可用时返回 503
        APIException: 执行失败时返回 500
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    try:
        return docker_manager.prune_unused_images()
    except RuntimeError:
        raise APIException("Docker 不可用", 503)
    except Exception as e:
        raise APIException(f"移除未使用镜像失败: {e}", 500)


@router.get("/images/search")
async def search_images(
    q: str,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜索镜像。

    使用当前默认配置的镜像搜索接口；无默认配置时使用 Docker Hub 官方 API。

    Args:
        q: 搜索关键词
        page: 页码，从 1 开始
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        dict: 包含 total、page、page_size、results 的分页结果

    Raises:
        APIException: 当所有镜像搜索源均不可用或解析失败时抛出
    """
    try:
        result = await db.execute(
            select(DockerMirrorConfig).where(DockerMirrorConfig.is_default == True)
        )
        config = result.scalar_one_or_none()
        if config:
            return docker_manager.search_images(
                q,
                page=page,
                api_url=config.search_api_url,
                mirror_url=config.mirror_url if config.enable_mirror else None,
                username=config.username,
                password=config.password,
            )
        # 无默认配置时使用 Docker Hub 官方 API
        return docker_manager.search_images(q, page=page)
    except RuntimeError as e:
        raise APIException(str(e), 503) from e
    except Exception as e:
        raise APIException(f"镜像搜索失败: {e}", 500) from e


@router.get("/images/tags", response_model=list[ImageTag])
async def get_image_tags(
    image: str,
    current_user: User = Depends(get_current_user),
):
    """获取指定镜像的可用标签列表。

    通过 Docker Hub API 查询镜像的所有可用 tags。

    Args:
        image: 镜像名称（不含标签，如 "nginx"）
        current_user: 当前登录用户

    Returns:
        list[ImageTag]: 标签列表
    """
    tags = docker_manager.get_image_tags(image)
    return tags


@router.post("/images/pull", response_model=PullTaskResponse)
async def pull_image(
    data: ImagePullRequest,
    current_user: User = Depends(get_current_user),
):
    """启动镜像拉取任务。

    在后台线程中流式拉取镜像，返回任务 ID 用于后续进度查询。

    Args:
        data: 拉取请求，包含镜像名称（含标签）
        current_user: 当前登录用户

    Returns:
        PullTaskResponse: 包含 task_id 和初始状态

    Raises:
        APIException: Docker 不可用时返回 503
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)

    try:
        task_id = task_manager.create_task(data.image)
    except RuntimeError as e:
        raise APIException(str(e), 429)

    # 在后台线程中执行拉取
    thread = threading.Thread(
        target=docker_manager.pull_image_async,
        args=(data.image, task_id, task_manager),
        daemon=True,
    )
    thread.start()

    return {
        "task_id": task_id,
        "image": data.image,
        "status": "pulling",
    }


@router.get("/images/pull/{task_id}/events")
async def pull_image_events(
    task_id: str,
    current_user: User = Depends(get_current_user_sse),
):
    """获取镜像拉取任务的实时进度（SSE）。

    建立 SSE 连接，先推送已缓存的进度，然后实时推送新进度。
    页面切换后重新连接可恢复进度。

    Args:
        task_id: 任务唯一标识
        current_user: 当前登录用户

    Returns:
        StreamingResponse: SSE 流

    Raises:
        APIException: 任务不存在时返回 404
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise APIException("任务不存在", 404)

    async def event_generator():
        """SSE 事件生成器。"""
        # 先发送已缓存的当前进度（已完成/失败时嵌入状态）
        _initial = task["progress"].copy()
        if task["status"] in ("completed", "failed"):
            _initial["_task_status"] = task["status"]
            if task.get("error"):
                _initial["_error"] = task["error"]
        yield f"data: {json.dumps(_initial, ensure_ascii=False)}\n\n"

        # 注册监听器队列接收实时更新
        q = task_manager.register_listener(task_id)
        try:
            while True:
                # 非阻塞取队列，超时 1 秒检查任务状态
                try:
                    progress = q.get(timeout=1)
                    yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    pass

                # 检查任务是否已完成或失败
                current_task = task_manager.get_task(task_id)
                if not current_task:
                    break
                if current_task["status"] in ("completed", "failed"):
                    # 发送最终状态后关闭（嵌入状态便于前端同步）
                    _final = current_task["progress"].copy()
                    _final["_task_status"] = current_task["status"]
                    if current_task.get("error"):
                        _final["_error"] = current_task["error"]
                    yield f"data: {json.dumps(_final, ensure_ascii=False)}\n\n"
                    break

                # 让出控制权，避免阻塞
                await asyncio.sleep(0.1)
        finally:
            task_manager.unregister_listener(task_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/images/pull/{task_id}/status", response_model=PullTaskStatus)
async def pull_image_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取镜像拉取任务的当前状态。

    用于页面切换后恢复进度（不通过 SSE 时也可轮询）。

    Args:
        task_id: 任务唯一标识
        current_user: 当前登录用户

    Returns:
        PullTaskStatus: 任务完整状态

    Raises:
        APIException: 任务不存在时返回 404
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise APIException("任务不存在", 404)
    return task


# ===================== 镜像搜索接口配置（Registry） =====================


@router.get("/registries", response_model=list[RegistryOut])
async def list_registries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有镜像搜索接口配置列表。

    Args:
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        list[RegistryOut]: 配置列表
    """
    result = await db.execute(select(DockerMirrorConfig).order_by(DockerMirrorConfig.id))
    configs = result.scalars().all()
    return configs


@router.post("/registries", response_model=RegistryOut)
async def create_registry(
    data: RegistryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建镜像搜索接口配置。

    如果是第一条配置，自动设为默认。

    Args:
        data: 创建请求数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        RegistryOut: 创建后的配置
    """
    config = DockerMirrorConfig(
        name=data.name,
        search_api_url=data.search_api_url,
        mirror_url=data.mirror_url,
        enable_mirror=data.enable_mirror,
        username=data.username,
        password=data.password,
    )
    # 如果是第一条配置，自动设为默认
    count_result = await db.execute(select(DockerMirrorConfig))
    if not count_result.scalars().first():
        config.is_default = True
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/registries/{registry_id}", response_model=RegistryOut)
async def update_registry(
    registry_id: int,
    data: RegistryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新镜像搜索接口配置。

    Args:
        registry_id: 配置记录 ID
        data: 更新请求数据
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        RegistryOut: 更新后的配置

    Raises:
        APIException: 配置不存在时返回 404
    """
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/registries/{registry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_registry(
    registry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除镜像搜索接口配置。

    默认配置不允许删除；删除默认配置前需先切换默认。

    Args:
        registry_id: 配置记录 ID
        db: 数据库会话
        current_user: 当前登录用户

    Raises:
        APIException: 配置不存在时返回 404
        APIException: 删除默认配置时返回 400
    """
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    if config.is_default:
        raise APIException("默认配置不允许删除，请先切换默认配置", 400)
    await db.delete(config)
    await db.commit()


@router.post("/registries/{registry_id}/set-default", response_model=RegistryOut)
async def set_default_registry(
    registry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将指定配置设为默认。

    会自动取消其他配置的默认状态。

    Args:
        registry_id: 配置记录 ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        RegistryOut: 更新后的配置

    Raises:
        APIException: 配置不存在时返回 404
    """
    result = await db.execute(
        select(DockerMirrorConfig).where(DockerMirrorConfig.id == registry_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise APIException("配置不存在", 404)
    # 取消其他配置的默认状态
    others = await db.execute(
        select(DockerMirrorConfig).where(
            DockerMirrorConfig.is_default == True,
            DockerMirrorConfig.id != registry_id,
        )
    )
    for other in others.scalars().all():
        other.is_default = False
    config.is_default = True
    await db.commit()
    await db.refresh(config)
    return config


# ===================== 批量删除 =====================


@router.post("/images/batch-delete")
async def batch_delete_images(
    data: BatchImageDeleteRequest,
    current_user: User = Depends(get_current_user),
):
    """批量删除本地镜像。

    Args:
        data: 批量删除请求，包含镜像 ID 列表和是否强制删除
        current_user: 当前登录用户

    Returns:
        dict: 包含 deleted 和 failed 两个列表的结果

    Raises:
        APIException: Docker 不可用或删除失败
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    if not data.ids:
        return {"deleted": [], "failed": []}
    try:
        result = docker_manager.remove_images(data.ids, force=data.force)
        return result
    except RuntimeError:
        raise APIException("Docker 不可用", 503)
    except Exception as e:
        raise APIException(f"批量删除镜像失败: {e}", 500)


# ===================== Compose 编排 =====================

from sqlalchemy.orm import selectinload
import json as _json


def _build_version_out(version: DockerComposeVersion | None) -> ComposeVersionOut | None:
    """将版本模型转换为响应 schema。"""
    if not version:
        return None
    return ComposeVersionOut(
        id=version.id,
        version_number=version.version_number,
        content=version.content,
        comment=version.comment,
        is_current=version.is_current,
        created_by_user_id=version.created_by_user_id,
        created_at=version.created_at.isoformat() if version.created_at else "",
    )


def _build_stack_out(
    stack: DockerComposeStack | None,
    status_info: dict | None = None,
) -> ComposeStackStatusOut | None:
    """将 Stack 状态模型转换为响应 schema。

    若传入 status_info（来自 docker compose ps 的实时解析结果），
    优先使用实时数据，避免列表页展示数据库缓存的过旧状态。
    """
    if status_info is not None:
        ports = sorted(status_info.get("ports", []))
        return ComposeStackStatusOut(
            status=status_info.get("status", "unknown"),
            service_count=status_info.get("service_count", 0),
            running_count=status_info.get("running_count", 0),
            ports=ports,
            last_action=stack.last_action if stack else None,
            last_action_at=stack.last_action_at.isoformat() if stack and stack.last_action_at else None,
            updated_at=stack.updated_at.isoformat() if stack and stack.updated_at else "",
        )
    if not stack:
        return None
    ports = []
    if stack.ports:
        try:
            ports = _json.loads(stack.ports)
        except _json.JSONDecodeError:
            ports = []
    return ComposeStackStatusOut(
        status=stack.status,
        service_count=stack.service_count,
        running_count=stack.running_count,
        ports=ports,
        last_action=stack.last_action,
        last_action_at=stack.last_action_at.isoformat() if stack.last_action_at else None,
        updated_at=stack.updated_at.isoformat() if stack.updated_at else "",
    )


def _build_project_out(
    project: DockerComposeProject,
    status_info: dict | None = None,
) -> ComposeProjectOut:
    """将项目模型转换为响应 schema。"""
    current_version = None
    for version in project.versions:
        if version.is_current:
            current_version = version
            break
    config_files = []
    if project.config_files:
        try:
            config_files = _json.loads(project.config_files)
        except _json.JSONDecodeError:
            config_files = []
    return ComposeProjectOut(
        id=project.id,
        project_name=project.project_name,
        description=project.description,
        is_active=project.is_active,
        current_version=_build_version_out(current_version),
        stack=_build_stack_out(project.stack, status_info=status_info),
        config_files=config_files or None,
        working_dir=project.working_dir,
        created_at=project.created_at.isoformat() if project.created_at else "",
        updated_at=project.updated_at.isoformat() if project.updated_at else "",
    )


async def _get_compose_project(
    db: AsyncSession, project_id: int
) -> DockerComposeProject:
    """获取项目，不存在时抛出 404。"""
    result = await db.execute(
        select(DockerComposeProject)
        .options(
            selectinload(DockerComposeProject.versions),
            selectinload(DockerComposeProject.stack),
        )
        .where(DockerComposeProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise APIException("编排项目不存在", 404)
    return project


@router.get("/compose", response_model=list[ComposeProjectOut])
async def list_compose_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有 Compose 项目列表。

    先扫描 Docker 容器自动发现/补全项目记录，再返回统一列表。
    Stack 状态会实时同步 docker compose ps，避免列表页展示过期状态。
    """
    # 自动发现系统外通过 docker compose 启动的项目
    await compose_manager.discover_projects(db)

    # 重新加载所有项目及其版本，避免异步懒加载问题
    result = await db.execute(
        select(DockerComposeProject)
        .options(
            selectinload(DockerComposeProject.versions),
            selectinload(DockerComposeProject.stack),
        )
        .order_by(DockerComposeProject.id.desc())
    )
    projects = result.scalars().all()

    async def _project_with_status(project: DockerComposeProject) -> ComposeProjectOut:
        try:
            status_info = await compose_manager.get_status(project)
        except Exception:
            # 实时状态获取失败时回退到数据库缓存，避免列表整体失败
            status_info = None
        return _build_project_out(project, status_info=status_info)

    return await asyncio.gather(*[_project_with_status(p) for p in projects])


@router.post("/compose", response_model=ComposeProjectOut, status_code=status.HTTP_201_CREATED)
async def create_compose_project(
    data: ComposeProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 Compose 项目。

    同时创建第一个版本并写入 compose 文件。
    """
    try:
        project = await compose_manager.create_project(
            db,
            project_name=data.project_name,
            content=data.content,
            user_id=current_user.id,
            description=data.description,
        )
    except IntegrityError:
        await db.rollback()
        raise APIException("项目名已存在", 409)
    except ValueError as e:
        raise APIException(str(e), 400)
    except Exception as e:
        raise APIException(f"创建项目失败: {e}", 500)

    project = await _get_compose_project(db, project.id)
    return _build_project_out(project)


@router.get("/compose/{project_id}", response_model=ComposeProjectOut)
async def get_compose_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个 Compose 项目详情。"""
    project = await _get_compose_project(db, project_id)
    return _build_project_out(project)


@router.put("/compose/{project_id}", response_model=ComposeProjectOut)
async def update_compose_project(
    project_id: int,
    data: ComposeProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Compose 项目元数据。"""
    project = await _get_compose_project(db, project_id)
    try:
        project = await compose_manager.update_project(
            db,
            project,
            description=data.description,
            is_active=data.is_active,
        )
    except Exception as e:
        raise APIException(f"更新项目失败: {e}", 500)
    return _build_project_out(project)


@router.post("/compose/{project_id}/edit", response_model=ComposeProjectOut)
async def edit_compose_project(
    project_id: int,
    data: ComposeEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑 Compose 项目并自动部署。

    保存新版本、更新 compose 文件并执行 docker compose up -d。
    """
    project = await _get_compose_project(db, project_id)
    try:
        await compose_manager.edit_and_deploy(
            db,
            project,
            content=data.content,
            user_id=current_user.id,
            comment=data.comment,
            description=data.description,
        )
    except ValueError as e:
        raise APIException(str(e), 400)
    except RuntimeError as e:
        raise APIException(str(e), 500)
    except Exception as e:
        raise APIException(f"编辑部署失败: {e}", 500)

    project = await _get_compose_project(db, project_id)
    return _build_project_out(project)


@router.delete("/compose/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_compose_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 Compose 项目。

    会先执行 docker compose down 清理容器和网络。
    """
    project = await _get_compose_project(db, project_id)
    try:
        await compose_manager.delete_project(db, project)
    except Exception as e:
        raise APIException(f"删除项目失败: {e}", 500)


@router.get("/compose/{project_id}/versions", response_model=list[ComposeVersionOut])
async def list_compose_versions(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目的所有版本列表。"""
    project = await _get_compose_project(db, project_id)
    return [_build_version_out(v) for v in project.versions]


@router.post("/compose/{project_id}/versions", response_model=ComposeVersionOut)
async def create_compose_version(
    project_id: int,
    data: ComposeVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为项目新增一个版本。"""
    project = await _get_compose_project(db, project_id)
    try:
        version = await compose_manager.add_version(
            db,
            project,
            content=data.content,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise APIException(str(e), 400)
    except Exception as e:
        raise APIException(f"新增版本失败: {e}", 500)
    return _build_version_out(version)


@router.post("/compose/{project_id}/versions/{version_id}/rollback", response_model=ComposeVersionOut)
async def rollback_compose_version(
    project_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """切换到指定版本。

    切换当前版本并自动执行 docker compose up -d 应用。
    """
    project = await _get_compose_project(db, project_id)
    version = next((v for v in project.versions if v.id == version_id), None)
    if not version:
        raise APIException("版本不存在", 404)
    try:
        version = await compose_manager.rollback_version(db, project, version)
    except RuntimeError as e:
        raise APIException(str(e), 500)
    except Exception as e:
        raise APIException(f"切换版本失败: {e}", 500)
    return _build_version_out(version)


@router.post("/compose/{project_id}/action")
async def compose_action(
    project_id: int,
    data: ComposeActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对 Compose 项目执行 up / down / restart 操作。"""
    project = await _get_compose_project(db, project_id)
    try:
        result = await compose_manager.action(db, project, data.action)
    except ValueError as e:
        raise APIException(str(e), 400)
    except RuntimeError as e:
        raise APIException(str(e), 500)
    except Exception as e:
        raise APIException(f"操作失败: {e}", 500)
    return {"success": True, "message": result["stdout"] or "ok"}


@router.get("/compose/{project_id}/status", response_model=ComposeStackStatusOut)
async def compose_status(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Compose 项目实时 Stack 状态。"""
    project = await _get_compose_project(db, project_id)
    try:
        stack = await compose_manager.sync_stack_status(db, project)
    except Exception as e:
        raise APIException(f"获取状态失败: {e}", 500)
    return _build_stack_out(stack)


@router.get("/compose/{project_id}/containers", response_model=list[ContainerInfo])
async def list_compose_containers(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Compose 项目维护的容器列表。

    通过 Docker Compose 标准标签 com.docker.compose.project 过滤归属容器。

    Args:
        project_id: Compose 项目 ID
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        list[ContainerInfo]: 归属该项目的容器信息列表

    Raises:
        APIException: 项目不存在时返回 404，Docker 不可用时返回 503
    """
    project = await _get_compose_project(db, project_id)
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)
    filters = {"label": [f"com.docker.compose.project={project.project_name}"]}
    return docker_manager.list_containers(filters=filters)


@router.get("/compose/{project_id}/logs")
async def compose_logs(
    project_id: int,
    tail: int = 100,
    services: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Compose 项目日志。

    services 参数使用逗号分隔服务名。
    """
    project = await _get_compose_project(db, project_id)
    service_list = services.split(",") if services else None
    try:
        logs = await compose_manager.get_logs(
            project, tail=tail, services=service_list
        )
    except RuntimeError as e:
        raise APIException(str(e), 500)
    except Exception as e:
        raise APIException(f"获取日志失败: {e}", 500)
    return {"logs": logs}


@router.get("/compose/{project_id}/logs/stream")
async def compose_logs_stream(
    project_id: int,
    tail: int = 100,
    follow: bool = True,
    services: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sse),
):
    """流式获取 Compose 项目日志（SSE）。

    建立 SSE 连接，实时推送 Compose 项目日志。

    Args:
        project_id: 项目 ID
        tail: 返回最后 N 行日志，默认 100
        follow: 是否持续跟踪新日志
        services: 指定服务名，逗号分隔
        db: 数据库会话
        current_user: 当前登录用户

    Returns:
        StreamingResponse: SSE 日志流

    Raises:
        APIException: 当 Docker 不可用时返回 503
        APIException: 当项目不存在时返回 404
    """
    if not docker_manager.available:
        raise APIException("Docker 不可用", 503)

    project = await _get_compose_project(db, project_id)
    service_list = services.split(",") if services else None

    async def event_generator():
        try:
            async for line in compose_manager.stream_logs(
                project, tail=tail, services=service_list, follow=follow
            ):
                yield f"data: {json.dumps({'line': line}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Compose 日志流异常")
            yield f"data: {json.dumps({'error': f'日志流异常: {e}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
