/**
 * 应用商店相关 React Query hooks
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/toast";
import type { ApiError } from "@/api/types";
import {
  listApps,
  getApp,
  deployApp,
  previewApp,
  createApp,
  updateApp,
  deleteApp,
  uploadAppIcon,
  previewAppTemplate,
  type App,
  type AppDetail,
  type DeployAppRequest,
  type AppPreviewRequest,
  type AppCreatePayload,
  type AppUpdatePayload,
  type AppTemplatePreviewRequest,
} from "@/api/apps";

// 保持既有导出，页面侧 import 路径无需变更
export type {
  App,
  AppDetail,
  DeployAppRequest,
  DeployAppResponse,
  AppPreviewRequest,
  AppPreviewResponse,
  AppCreatePayload,
  AppUpdatePayload,
  AppTemplatePreviewRequest,
} from "@/api/apps";

/**
 * 查询所有应用商店应用
 */
export function useApps(category?: string, tag?: string) {
  return useQuery<App[]>({
    queryKey: ["apps", { category, tag }],
    queryFn: () => listApps({ category, tag }),
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
    queryFn: () => getApp(name),
    enabled: options?.enabled ?? !!name,
    staleTime: options?.staleTime,
    refetchOnMount: "always",
  });
}

/**
 * 一键部署应用（异步）
 *
 * 后端立即返回任务 ID，调用方需自行监听部署进度。
 */
export function useDeployApp() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: DeployAppRequest }) =>
      deployApp(name, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
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
  return useMutation({
    mutationFn: (data: AppPreviewRequest) => previewApp(name, data),
  });
}

/**
 * 创建应用（仅管理员）
 */
export function useCreateApp() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (data: AppCreatePayload) => createApp(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["apps"] });
      toast.success("应用创建成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "创建失败");
    },
  });
}

/**
 * 更新应用（仅管理员）
 */
export function useUpdateApp() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: AppUpdatePayload }) =>
      updateApp(name, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["apps"] });
      toast.success("应用保存成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "保存失败");
    },
  });
}

/**
 * 删除应用（仅管理员）
 */
export function useDeleteApp() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (name: string) => deleteApp(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["apps"] });
      toast.success("应用已删除");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "删除失败");
    },
  });
}

/**
 * 上传应用图标（仅管理员）
 */
export function useUploadAppIcon() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ name, file }: { name: string; file: File }) =>
      uploadAppIcon(name, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["apps"] });
      toast.success("图标上传成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "图标上传失败");
    },
  });
}

/**
 * 预览未落库的应用模板渲染结果（创建/编辑页用）
 */
export function useAppTemplatePreview() {
  return useMutation({
    mutationFn: (data: AppTemplatePreviewRequest) => previewAppTemplate(data),
  });
}
