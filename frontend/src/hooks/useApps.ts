/**
 * 应用商店相关 React Query hooks
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";

/** API 错误对象 */
interface ApiError {
  displayMessage?: string;
}

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
  source_dir: string | null;
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
  instance_id: number;
  project_id: number;
  project_name: string;
  instance_name: string;
  status: string;
  pending_config: Record<string, unknown>;
}

/** 预览请求 */
export interface AppPreviewRequest {
  instance_name: string;
  config: Record<string, unknown>;
}

/** 预览响应 */
export interface AppPreviewResponse {
  yaml: string;
}

/**
 * 查询所有应用商店应用
 */
export function useApps(category?: string, tag?: string) {
  return useQuery<App[]>({
    queryKey: ["apps", { category, tag }],
    queryFn: () => api.get("/apps", { params: { category, tag } }).then((r) => r.data),
  });
}

/**
 * 查询单个应用详情
 */
export function useApp(
  name: string,
  options?: { enabled?: boolean; staleTime?: number }
) {
  return useQuery<AppDetail>({
    queryKey: ["apps", name],
    queryFn: () => api.get(`/apps/${name}`).then((r) => r.data),
    enabled: options?.enabled ?? !!name,
    staleTime: options?.staleTime,
    refetchOnMount: "always",
  });
}

/**
 * 一键部署应用
 */
export function useDeployApp() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({
      name,
      data,
    }: {
      name: string;
      data: DeployAppRequest;
    }) => api.post<DeployAppResponse>(`/apps/${name}/deploy`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      toast.success("部署成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "部署失败");
    },
  });
}

/**
 * 预览应用渲染后的 Compose YAML
 */
export function useAppPreview(name: string) {
  const toast = useToast();
  return useMutation({
    mutationFn: (data: AppPreviewRequest) =>
      api.post<AppPreviewResponse>(`/apps/${name}/preview`, data).then((r) => r.data.yaml),
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "预览失败");
    },
  });
}
