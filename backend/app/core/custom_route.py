"""自定义 API 路由，自动包装成功响应为标准格式。"""

from typing import Callable
import json

from fastapi.routing import APIRoute
from fastapi import Request, Response
from starlette.responses import JSONResponse

from app.schemas.response import StandardResponse


class CustomAPIRoute(APIRoute):
    """自定义路由，自动将成功响应包装为 StandardResponse 格式。

    跳过以下响应类型：
    - 204 No Content（空响应体）
    - 已经是 StandardResponse 格式的响应
    - 非 JSONResponse 类型（如 StreamingResponse）
    """

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            response = await original_route_handler(request)

            # 跳过 204 No Content 响应
            if isinstance(response, Response) and response.status_code == 204:
                return response

            # 跳过已经是 StandardResponse 格式的响应
            if isinstance(response, JSONResponse) and hasattr(response, "body"):
                try:
                    body_data = json.loads(response.body)
                    if (
                        isinstance(body_data, dict)
                        and "success" in body_data
                        and "data" in body_data
                        and "message" in body_data
                        and isinstance(body_data["success"], bool)
                    ):
                        return response
                except (json.JSONDecodeError, TypeError):
                    pass

            # 包装 JSON 成功响应
            if isinstance(response, JSONResponse):
                body = response.body
                data = json.loads(body)
                wrapped = StandardResponse.ok(data=data)
                # 移除原始 Content-Length，让 Starlette 重新计算
                headers = {
                    k: v for k, v in response.headers.items()
                    if k.lower() != "content-length"
                }
                return JSONResponse(
                    content=wrapped.model_dump(),
                    status_code=response.status_code,
                    headers=headers,
                )

            return response

        return custom_route_handler
