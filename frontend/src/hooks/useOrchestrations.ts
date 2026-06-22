/**
 * 应用编排相关 React Query hooks
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";

/** API 错误对象 */
interface ApiError {
  displayMessage?: string;
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
  architectures: string[];
  config_schema: Record<string, unknown>;
  version: string;
  is_builtin: boolean;
  type: "compose" | "container";
  changelog: string | null;
  backup_paths: string[];
  source_dir: string | null;
}

/** 应用编排详情 */
export interface AppOrchestrationDetail extends AppOrchestration {
  readme: string | null;
  suggested_plugins: string[];
}

/** 部署请求 */
export interface DeployOrchestrationRequest {
  instance_name: string;
  config: Record<string, unknown>;
}

/** 部署响应 */
export interface DeployOrchestrationResponse {
  instance_id: number;
  project_id: number;
  project_name: string;
  instance_name: string;
  status: string;
  pending_config: Record<string, unknown>;
}

/**
 * 查询所有应用编排
 */
export function useOrchestrations(category?: string, tag?: string) {
  return useQuery<AppOrchestration[]>({
    queryKey: ["orchestrations", { category, tag }],
    queryFn: () =>
      api
        .get("/orchestrations", { params: { category, tag } })
        .then((r) => r.data),
  });
}

/**
 * 查询单个应用编排详情
 */
export function useOrchestration(name: string) {
  return useQuery<AppOrchestrationDetail>({
    queryKey: ["orchestrations", name],
    queryFn: () => api.get(`/orchestrations/${name}`).then((r) => r.data),
    enabled: !!name,
  });
}

/**
 * 一键部署应用编排
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
    }) => api.post<DeployOrchestrationResponse>(`/orchestrations/${name}/deploy`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      toast.success("部署成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "部署失败");
    },
  });
}
