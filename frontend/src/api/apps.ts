/**
 * 应用商店相关 API
 */

import api from "@/lib/api";

/** 应用商店应用信息 */
export interface App {
  id: number;
  name: string;
  display_name: string;
  description: string | null;
  category: string;
  tags: string[];
  icon: string | null;
  website: string | null;
  source_url: string | null;
  architectures: string[];
  image: string | null;
  default_ports: { port: number; protocol?: string; description?: string }[];
  config_schema: Record<string, unknown>;
  version: string;
  is_builtin: boolean;
  type: "compose" | "container";
  changelog: string | null;
  backup_paths: string[];
}

/** 应用详情 */
export interface AppDetail extends App {
  readme: string | null;
  yaml_template: string | null;
}

/** 部署请求 */
export interface DeployAppRequest {
  instance_name: string;
  config: Record<string, unknown>;
}

/** 部署响应 */
export interface DeployAppResponse {
  task_id: string;
  /** 应用实例 ID（异步任务，可能尚未创建） */
  instance_id: number | null;
  /** Compose 项目 ID（异步任务，可能尚未创建） */
  project_id?: number | null;
  status: string;
}

/** 预览请求 */
export interface AppPreviewRequest {
  instance_name: string;
  config: Record<string, unknown>;
}

/** 预览响应 */
export interface AppPreviewResponse {
  yaml: string | null;
  error: string | null;
}

/** 创建应用请求（与后端 AppCreate 对齐） */
export interface AppCreatePayload {
  name: string;
  display_name: string;
  description?: string | null;
  category?: string;
  tags?: string[];
  icon?: string | null;
  website?: string | null;
  source_url?: string | null;
  architectures?: string[];
  image?: string | null;
  default_ports?: { port: number; protocol?: string; description?: string }[];
  config_schema?: Record<string, unknown>;
  yaml_template: string;
  readme?: string | null;
  version?: string;
  type?: string;
  changelog?: string | null;
  backup_paths?: string[];
}

/** 更新应用请求（所有字段可选，name 不可修改） */
export type AppUpdatePayload = Partial<Omit<AppCreatePayload, "name">>;

/** 未落库模板预览请求 */
export interface AppTemplatePreviewRequest {
  yaml_template: string;
  config_schema?: Record<string, unknown>;
  image?: string | null;
  app_name?: string;
}

/** 查询应用列表 */
export function listApps(params?: { category?: string; tag?: string }) {
  return api.get<App[]>("/apps", { params }).then((r) => r.data);
}

/** 查询单个应用详情 */
export function getApp(name: string, signal?: AbortSignal) {
  return api.get<AppDetail>(`/apps/${name}`, { signal }).then((r) => r.data);
}

/** 一键部署应用（异步，返回任务 ID） */
export function deployApp(name: string, data: DeployAppRequest) {
  return api
    .post<DeployAppResponse>(`/apps/${name}/deploy`, data)
    .then((r) => r.data);
}

/** 预览应用渲染后的 Compose YAML */
export function previewApp(
  name: string,
  data: AppPreviewRequest,
  signal?: AbortSignal
) {
  return api
    .post<AppPreviewResponse>(`/apps/${name}/preview`, data, { signal })
    .then((r) => r.data);
}

/** 创建应用（仅管理员） */
export function createApp(data: AppCreatePayload) {
  return api.post<AppDetail>("/apps", data).then((r) => r.data);
}

/** 更新应用（仅管理员） */
export function updateApp(name: string, data: AppUpdatePayload) {
  return api.put<AppDetail>(`/apps/${name}`, data).then((r) => r.data);
}

/** 删除应用（仅管理员） */
export function deleteApp(name: string) {
  return api.delete(`/apps/${name}`).then((r) => r.data);
}

/** 上传应用图标（仅管理员），保存后 app.icon 指向后端图标接口 */
export function uploadAppIcon(name: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return api
    .post<AppDetail>(`/apps/${name}/icon`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
}

/** 预览未落库的应用模板渲染结果（仅管理员，创建/编辑页用） */
export function previewAppTemplate(
  data: AppTemplatePreviewRequest,
  signal?: AbortSignal
) {
  return api
    .post<AppPreviewResponse>("/apps/preview-template", data, { signal })
    .then((r) => r.data);
}
