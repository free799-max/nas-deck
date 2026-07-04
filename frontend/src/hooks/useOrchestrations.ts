/**
 * 应用编排（自动化组合模板）相关 React Query hooks
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";

/** API 错误对象 */
interface ApiError {
  displayMessage?: string;
}

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

/**
 * 查询应用编排列表，支持分类筛选
 */
export function useOrchestrations(category?: string) {
  return useQuery<AppOrchestration[]>({
    queryKey: ["orchestrations", { category }],
    queryFn: () =>
      api
        .get("/orchestrations", { params: { category } })
        .then((r) => r.data),
  });
}

/**
 * 查询单个应用编排详情
 */
export function useOrchestration(name: string) {
  return useQuery<AppOrchestration>({
    queryKey: ["orchestrations", name],
    queryFn: () => api.get(`/orchestrations/${name}`).then((r) => r.data),
    enabled: !!name,
  });
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

/**
 * 查询编排实例组列表，支持分类筛选
 */
export function useOrchestrationInstances(category?: string) {
  return useQuery<OrchestrationInstanceGroup[]>({
    queryKey: ["orchestration-instances", { category }],
    queryFn: () =>
      api
        .get("/orchestrations/instances", { params: { category } })
        .then((r) => r.data),
  });
}

/**
 * 查询单个编排实例组详情
 */
export function useOrchestrationInstanceDetail(instanceId: number | null) {
  return useQuery<OrchestrationInstanceDetail>({
    queryKey: ["orchestration-instances", instanceId, "detail"],
    queryFn: () =>
      api.get(`/orchestrations/instances/${instanceId}`).then((r) => r.data),
    enabled: !!instanceId,
  });
}

/**
 * 更新编排实例组信息
 */
export function useUpdateOrchestrationInstance() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: OrchestrationInstanceUpdatePayload;
    }) =>
      api
        .patch<OrchestrationInstanceDetail>(`/orchestrations/instances/${id}`, data)
        .then((r) => r.data as OrchestrationInstanceDetail),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["orchestration-instances"] });
      qc.invalidateQueries({
        queryKey: ["orchestration-instances", variables.id, "detail"],
      });
      toast.success("实例组已更新");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "更新失败");
    },
  });
}

/**
 * 删除编排实例组
 */
export function useDeleteOrchestrationInstance() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (id: number) =>
      api.delete(`/orchestrations/instances/${id}`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orchestration-instances"] });
      toast.success("实例组已删除");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "删除失败");
    },
  });
}

/**
 * 查询可导入的 Docker 容器候选
 */
export function useImportCandidates(name: string) {
  return useQuery<ImportCandidateApp[]>({
    queryKey: ["orchestrations", name, "import-candidates"],
    queryFn: () =>
      api.get(`/orchestrations/${name}/import-candidates`).then((r) => r.data),
    enabled: !!name,
  });
}

/**
 * 导入已有 Docker 部署为编排实例
 */
export function useImportOrchestration() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({
      name,
      data,
    }: {
      name: string;
      data: OrchestrationImportRequest;
    }) =>
      api
        .post<OrchestrationImportResponse>(`/orchestrations/${name}/import`, data)
        .then((r) => r.data as OrchestrationImportResponse),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["apps", "instances"] });
      qc.invalidateQueries({ queryKey: ["orchestrations"] });
      qc.invalidateQueries({
        queryKey: ["orchestration-instances"],
      });
      qc.invalidateQueries({
        queryKey: ["orchestrations", variables.name, "import-candidates"],
      });
      toast.success("导入成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "导入失败");
    },
  });
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

/**
 * 验证应用访问地址与认证信息
 */
export function useVerifyAppAuth() {
  const toast = useToast();
  return useMutation({
    mutationFn: (data: AppAuthVerifyRequest) =>
      api
        .post<AppAuthVerifyResponse>("/orchestrations/auth/verify", data)
        .then((r) => r.data as AppAuthVerifyResponse),
    onSuccess: (data) => {
      if (data.valid) {
        toast.success(data.message || "认证检测通过");
      } else {
        toast.error(data.message || "认证检测失败");
      }
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "认证检测请求失败");
    },
  });
}

/**
 * 组合部署应用编排
 */
export function useDeployOrchestration() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({
      name,
      data,
    }: {
      name: string;
      data: DeployOrchestrationRequest;
    }) =>
      api.post<DeployOrchestrationResponse>(`/orchestrations/${name}/deploy`, data).then((r) => r.data as DeployOrchestrationResponse),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      qc.invalidateQueries({ queryKey: ["apps", "instances"] });
      qc.invalidateQueries({ queryKey: ["orchestration-instances"] });
      toast.success("组合部署已启动");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "部署失败");
    },
  });
}
