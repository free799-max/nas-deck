/**
 * 应用编排（自动化组合模板）相关 API
 */

import api from "@/lib/api";

/** 组合中的应用定义 */
export interface AppCompositionItem {
  app_name: string;
  relation: "required" | "optional" | "suggested" | "conflicting";
  group?: string | null;
  conflict_with?: string[];
}

/** 应用编排信息 */
export interface AppOrchestration {
  id: number;
  name: string;
  display_name: string;
  description: string | null;
  category: string;
  tags: string[];
  icon: string | null;
  website: string | null;
  source_url: string | null;
  version: string;
  is_builtin: boolean;
  app_composition: AppCompositionItem[];
  shared_config_schema: Record<string, unknown>;
}

/** 部署请求 */
export interface DeployOrchestrationRequest {
  instance_name: string;
  selected_apps: string[];
  app_configs: Record<string, Record<string, unknown>>;
  shared_config: Record<string, unknown>;
}

/** 部署响应 */
export interface DeployOrchestrationResponse {
  group_id: number;
  instance_name: string;
  status: string;
  task_ids: string[];
}

/** 单个容器匹配信息 */
export interface ContainerMatch {
  container_id: string;
  container_name: string;
  image: string;
  network_ip: string | null;
  host_port: number | null;
  container_port: string | null;
  suggested_url: string | null;
}

/** 可导入应用候选 */
export interface ImportCandidateApp {
  app_name: string;
  display_name: string;
  icon: string | null;
  relation: string;
  group: string | null;
  matched: boolean;
  candidates: ContainerMatch[];
}

/** 单个应用导入配置 */
export interface OrchestrationImportAppConfig {
  selected_container_id?: string | null;
  auth_type?: "none" | "basic" | "api_key";
  url?: string | null;
  username?: string | null;
  password?: string | null;
  api_key?: string | null;
}

/** 导入请求 */
export interface OrchestrationImportRequest {
  instance_name: string;
  selected_apps: string[];
  app_configs: Record<string, OrchestrationImportAppConfig>;
  shared_config: Record<string, unknown>;
}

/** 导入响应 */
export interface OrchestrationImportResponse {
  group_id: number;
  instance_name: string;
  status: string;
  created_app_instance_ids: number[];
}

/** 编排实例组中的应用 */
export interface OrchestrationInstanceApp {
  id: number;
  app_name: string;
  display_name: string;
  icon: string | null;
  status: string;
  config: Record<string, unknown>;
}

/** 编排实例组（一次部署/导入记录） */
export interface OrchestrationInstanceGroup {
  id: number;
  instance_name: string;
  orchestration_name: string;
  orchestration_display_name: string;
  status: string;
  created_at: string;
  apps: OrchestrationInstanceApp[];
}

/** 编排实例组详情 */
export interface OrchestrationInstanceDetail
  extends OrchestrationInstanceGroup {
  shared_config: Record<string, unknown>;
  app_configs: Record<string, Record<string, unknown>>;
}

/** 更新编排实例组请求 */
export interface OrchestrationInstanceUpdatePayload {
  instance_name?: string;
  shared_config?: Record<string, unknown>;
  app_configs?: Record<string, Record<string, unknown>>;
}

/** 应用认证检测请求 */
export interface AppAuthVerifyRequest {
  app_name: string;
  url: string;
  auth_type: "none" | "basic" | "api_key";
  username?: string;
  password?: string;
  api_key?: string;
}

/** 应用认证检测响应 */
export interface AppAuthVerifyResponse {
  valid: boolean;
  message?: string;
}

/** 查询应用编排列表，支持分类筛选 */
export function listOrchestrations(category?: string) {
  return api
    .get<AppOrchestration[]>("/orchestrations", { params: { category } })
    .then((r) => r.data);
}

/** 查询单个应用编排详情 */
export function getOrchestration(name: string) {
  return api.get<AppOrchestration>(`/orchestrations/${name}`).then((r) => r.data);
}

/** 查询编排实例组列表，支持分类筛选 */
export function listOrchestrationInstances(category?: string) {
  return api
    .get<OrchestrationInstanceGroup[]>("/orchestrations/instances", {
      params: { category },
    })
    .then((r) => r.data);
}

/** 查询单个编排实例组详情 */
export function getOrchestrationInstanceDetail(instanceId: number) {
  return api
    .get<OrchestrationInstanceDetail>(`/orchestrations/instances/${instanceId}`)
    .then((r) => r.data);
}

/** 更新编排实例组信息 */
export function updateOrchestrationInstance(
  id: number,
  data: OrchestrationInstanceUpdatePayload
) {
  return api
    .patch<OrchestrationInstanceDetail>(`/orchestrations/instances/${id}`, data)
    .then((r) => r.data);
}

/** 删除编排实例组 */
export function deleteOrchestrationInstance(id: number) {
  return api.delete(`/orchestrations/instances/${id}`).then((r) => r.data);
}

/** 查询可导入的 Docker 容器候选 */
export function getImportCandidates(name: string) {
  return api
    .get<ImportCandidateApp[]>(`/orchestrations/${name}/import-candidates`)
    .then((r) => r.data);
}

/** 导入已有 Docker 部署为编排实例 */
export function importOrchestration(
  name: string,
  data: OrchestrationImportRequest
) {
  return api
    .post<OrchestrationImportResponse>(`/orchestrations/${name}/import`, data)
    .then((r) => r.data);
}

/** 验证应用访问地址与认证信息 */
export function verifyAppAuth(data: AppAuthVerifyRequest) {
  return api
    .post<AppAuthVerifyResponse>("/orchestrations/auth/verify", data)
    .then((r) => r.data);
}

/** 组合部署应用编排 */
export function deployOrchestration(
  name: string,
  data: DeployOrchestrationRequest
) {
  return api
    .post<DeployOrchestrationResponse>(`/orchestrations/${name}/deploy`, data)
    .then((r) => r.data);
}
