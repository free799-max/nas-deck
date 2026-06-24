/**
 * 系统设置相关 React Query hooks
 *
 * 提供系统全局配置的查询和更新能力。
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";

/** API 错误对象 */
interface ApiError {
  displayMessage?: string;
}

/** 系统全局配置（前端使用空字符串代替 null） */
export interface SystemConfig {
  id: number;
  http_proxy: string;
  https_proxy: string;
  no_proxy: string;
  storage_host_root_dir: string;
  storage_docker_mount_dir: string;
}

/** 系统配置更新请求 */
export interface SystemConfigUpdate {
  http_proxy?: string | null;
  https_proxy?: string | null;
  no_proxy?: string | null;
  storage_host_root_dir?: string | null;
  storage_docker_mount_dir?: string | null;
}

/** 目录列表响应 */
export interface DirectoryList {
  path: string;
  entries: { name: string; path: string; is_directory: boolean }[];
}

/**
 * 查询系统全局配置
 */
export function useSystemConfig() {
  return useQuery<SystemConfig>({
    queryKey: ["settings", "system-config"],
    queryFn: () => api.get("/settings").then((r) => r.data),
  });
}

/**
 * 更新系统全局配置
 */
export function useUpdateSystemConfig() {
  const qc = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (data: SystemConfigUpdate) =>
      api.put("/settings", data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings", "system-config"] });
      toast.success("保存成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "保存失败");
    },
  });
}

/**
 * 查询宿主机指定路径下的目录列表（设置页专用）
 */
export function useSettingsDirectories(path: string, enabled = true) {
  return useQuery<DirectoryList>({
    queryKey: ["settings", "directories", path],
    queryFn: () =>
      api
        .get("/settings/directories", { params: { path } })
        .then((r) => r.data),
    enabled: enabled && !!path,
    staleTime: 0,
  });
}
