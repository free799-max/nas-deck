/**
 * 系统设置相关 React Query hooks
 *
 * 提供系统全局配置的查询和更新能力。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/toast";
import type { ApiError } from "@/api/types";
import {
  getSystemConfig,
  updateSystemConfig,
  type SystemConfig,
  type SystemConfigUpdate,
} from "@/api/settings";
import {
  settingsDirectoriesApi,
  type DirectoryList,
  type CreateDirectoryRequest,
  type RenameDirectoryRequest,
  type DeleteDirectoryRequest,
} from "@/api/directories";

// 保持既有导出，页面侧 import 路径无需变更
export type { SystemConfig, SystemConfigUpdate } from "@/api/settings";
export type {
  DirectoryList,
  CreateDirectoryRequest,
  RenameDirectoryRequest,
  DeleteDirectoryRequest,
} from "@/api/directories";

/**
 * 查询系统全局配置
 */
export function useSystemConfig() {
  return useQuery<SystemConfig>({
    queryKey: ["settings", "system-config"],
    queryFn: getSystemConfig,
  });
}

/**
 * 更新系统全局配置
 */
export function useUpdateSystemConfig() {
  const qc = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (data: SystemConfigUpdate) => updateSystemConfig(data),
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
    queryFn: () => settingsDirectoriesApi.list(path),
    enabled: enabled && !!path,
    staleTime: 0,
  });
}

/**
 * 创建目录（设置端点）
 */
export function useSettingsCreateDirectory() {
  const qc = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (data: CreateDirectoryRequest) =>
      settingsDirectoriesApi.create(data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({
        queryKey: ["settings", "directories", vars.path],
      });
      toast.success("创建成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "创建失败");
    },
  });
}

/**
 * 重命名目录（设置端点）
 */
export function useSettingsRenameDirectory() {
  const qc = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (data: RenameDirectoryRequest) =>
      settingsDirectoriesApi.rename(data),
    onSuccess: (_, vars) => {
      const parent = vars.old_path.replace(/\/[^/]*\/?$/, "") || "/";
      qc.invalidateQueries({
        queryKey: ["settings", "directories", parent],
      });
      toast.success("重命名成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "重命名失败");
    },
  });
}

/**
 * 删除目录（设置端点）
 */
export function useSettingsDeleteDirectory() {
  const qc = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (data: DeleteDirectoryRequest) =>
      settingsDirectoriesApi.remove(data),
    onSuccess: (_, vars) => {
      const parent = vars.path.replace(/\/[^/]*\/?$/, "") || "/";
      qc.invalidateQueries({
        queryKey: ["settings", "directories", parent],
      });
      toast.success("删除成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "删除失败");
    },
  });
}
