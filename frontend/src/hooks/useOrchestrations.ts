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
      toast.success("组合部署已启动");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "部署失败");
    },
  });
}
