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
