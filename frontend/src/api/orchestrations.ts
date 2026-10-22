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

/** 编排实例组 */
export interface OrchestrationInstanceGroup {
  id: number;
  instance_name: string;
  orchestration_name: string;
  orchestration_display_name: string;
  status: string;
  created_at: string;
  apps: OrchestrationInstanceApp[];
}

/** 备份中的应用数据目录 */
export interface OrchestrationBackupApp {
  app_name: string;
  instance_name?: string | null;
}

/** 可恢复的实例组备份 */
export interface OrchestrationBackup {
  name: string;
  instance_name: string;
  orchestration_name?: string | null;
  deleted_at?: string | null;
  apps: OrchestrationBackupApp[];
}

/** 从备份恢复请求 */
export interface RestoreOrchestrationRequest {
  backup: string;
  instance_name?: string | null;
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

/** 检测项状态 */
export type InspectItemStatus = "ok" | "warn" | "error";

/** 应用配置健康检测项 */
export interface AppInspectItem {
  id: string;
  title: string;
  status: InspectItemStatus;
  message?: string | null;
  current_value?: string | null;
  expected_value?: string | null;
  fixable: boolean;
  /** 展示分组（可选），如「核心配置」 */
  category?: string | null;
}

/** 应用配置健康检测报告 */
export interface AppInspectReport {
  supported: boolean;
  items: AppInspectItem[];
}

/** 单个检测项的自动修复结果 */
export interface AppFixResultItem {
  id: string;
  ok: boolean;
  message?: string | null;
}

/** 检测项自动修复响应 */
export interface AppFixResponse {
  results: AppFixResultItem[];
}

/** 应用插件（MoviePilot 原始结构透传，字段做容错读取） */
export interface AppPlugin {
  id?: string;
  plugin_id?: string;
  plugin_name?: string;
  plugin_desc?: string;
  plugin_version?: string;
  plugin_author?: string;
  repo_url?: string;
  installed?: boolean;
  [key: string]: unknown;
}

/** 应用插件列表响应 */
export interface AppPluginsResponse {
  installed: AppPlugin[];
  market: AppPlugin[];
}

/** 装配记录（下载器/媒体服务器） */
export interface IntegrationRecord {
  name: string;
  type?: string;
  url?: string | null;
  status: "ok" | "error";
  message?: string;
  webhook_url?: string;
}

/** 应用间自动装配结果（存于 app_configs[目标应用].integrations） */
export interface AppIntegrations {
  wired_at?: string;
  downloaders: IntegrationRecord[];
  mediaservers: IntegrationRecord[];
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

/** 删除实例组响应（后台任务） */
export interface DeleteOrchestrationResponse {
  task_id: string;
}

/** 删除编排实例组（后台任务，返回任务 ID） */
export function deleteOrchestrationInstance(id: number) {
  return api
    .delete<DeleteOrchestrationResponse>(`/orchestrations/instances/${id}`)
    .then((r) => r.data);
}

/** 列出可恢复的实例组备份 */
export function listOrchestrationBackups(orchestration?: string) {
  return api
    .get<OrchestrationBackup[]>("/orchestrations/backups", {
      params: { orchestration },
    })
    .then((r) => r.data);
}

/** 从备份恢复实例组（移回数据目录并重新部署） */
export function restoreOrchestrationBackup(data: RestoreOrchestrationRequest) {
  return api
    .post<DeployOrchestrationResponse>(
      "/orchestrations/backups/restore",
      data
    )
    .then((r) => r.data);
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

/** 修复编排实例组（重新部署失败/卡死的应用） */
export function redeployOrchestrationInstance(
  id: number,
  data: DeployOrchestrationRequest
) {
  return api
    .post<DeployOrchestrationResponse>(
      `/orchestrations/instances/${id}/redeploy`,
      data
    )
    .then((r) => r.data);
}

/** 手动重跑应用间自动装配（后台执行，立即返回） */
export function wireOrchestrationInstance(id: number) {
  return api
    .post<{ ok: boolean; message?: string }>(
      `/orchestrations/instances/${id}/wire`
    )
    .then((r) => r.data);
}

/** 对组内指定应用执行配置健康检测 */
export function inspectOrchestrationApp(instanceId: number, appName: string) {
  return api
    .get<AppInspectReport>(
      `/orchestrations/instances/${instanceId}/apps/${appName}/inspect`
    )
    .then((r) => r.data);
}

/** 对组内指定应用的检测项执行自动修复 */
export function fixOrchestrationAppInspect(
  instanceId: number,
  appName: string,
  itemIds: string[]
) {
  return api
    .post<AppFixResponse>(
      `/orchestrations/instances/${instanceId}/apps/${appName}/inspect/fix`,
      { item_ids: itemIds }
    )
    .then((r) => r.data);
}

/** 查询应用已安装插件与插件市场列表（当前仅 MoviePilot 支持） */
export function listOrchestrationAppPlugins(
  instanceId: number,
  appName: string
) {
  return api
    .get<AppPluginsResponse>(
      `/orchestrations/instances/${instanceId}/apps/${appName}/plugins`
    )
    .then((r) => r.data);
}

/** 安装应用插件（当前仅 MoviePilot 支持） */
export function installOrchestrationAppPlugin(
  instanceId: number,
  appName: string,
  data: { plugin_id: string; repo_url?: string }
) {
  return api
    .post<{ ok: boolean; message?: string }>(
      `/orchestrations/instances/${instanceId}/apps/${appName}/plugins/install`,
      data
    )
    .then((r) => r.data);
}
