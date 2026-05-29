# NasDeck 项目记忆

## API 响应格式规范

项目采用统一的 `StandardResponse` 格式：

```json
// 成功
{ "success": true, "data": ..., "message": "ok" }

// 错误
{ "success": false, "data": null, "message": "错误描述" }
```

**关键约定**:
- 后端路由层直接返回数据，`CustomAPIRoute` 自动包装
- 业务异常统一使用 `APIException`，禁止使用 `HTTPException`
- 204 No Content 保持空响应体，不包装
- 前端 Axios 拦截器自动解包 `data` 字段
- 错误消息通过 `error.displayMessage` 传递给页面层

**核心文件**:
- `backend/app/schemas/response.py` — `StandardResponse[T]`
- `backend/app/core/exceptions.py` — `APIException`
- `backend/app/core/custom_route.py` — 自动包装路由
- `frontend/src/lib/api.ts` — Axios 解包拦截器

完整规范见 `docs/api/api-response-spec.md`。
