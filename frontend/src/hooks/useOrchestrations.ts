/**
 * 应用编排（自动化组合模板）相关 React Query hooks
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/toast";
import type { ApiError } from "@/api/types";
import * as orchestrationsApi from "@/api/orchestrations";
import type {
  AppOrchestration,
  DeployOrchestrationRequest,
  ImportCandidateApp,
  OrchestrationImportRequest,
  OrchestrationInstanceGroup,
  OrchestrationInstanceDetail,
  OrchestrationInstanceUpdatePayload,
  AppAuthVerifyRequest,
  AppInspectReport,
  AppPluginsResponse,
} from "@/api/orchestrations";

// 保持既有导出，页面侧 import 路径无需变更
export type {
  AppCompositionItem,
  AppOrchestration,
  DeployOrchestrationRequest,
  DeployOrchestrationResponse,
  ContainerMatch,
  ImportCandidateApp,
  OrchestrationImportAppConfig,
  OrchestrationImportRequest,
  OrchestrationImportResponse,
  OrchestrationInstanceApp,
  OrchestrationInstanceGroup,
  OrchestrationInstanceDetail,
  OrchestrationInstanceUpdatePayload,
  AppAuthVerifyRequest,
  AppAuthVerifyResponse,
  InspectItemStatus,
  AppInspectItem,
  AppInspectReport,
  AppFixResultItem,
  AppFixResponse,
  AppPlugin,
  AppPluginsResponse,
  IntegrationRecord,
  AppIntegrations,
} from "@/api/orchestrations";

/**
 * 查询应用编排列表，支持分类筛选
 */
export function useOrchestrations(category?: string) {
  return useQuery<AppOrchestration[]>({
    queryKey: ["orchestrations", { category }],
    queryFn: () => orchestrationsApi.listOrchestrations(category),
  });
}

/**
 * 查询单个应用编排详情
 */
export function useOrchestration(name: string) {
  return useQuery<AppOrchestration>({
    queryKey: ["orchestrations", name],
    queryFn: () => orchestrationsApi.getOrchestration(name),
    enabled: !!name,
  });
}

/**
 * 查询编排实例组列表，支持分类筛选
 */
export function useOrchestrationInstances(category?: string) {
  return useQuery<OrchestrationInstanceGroup[]>({
    queryKey: ["orchestration-instances", { category }],
    queryFn: () => orchestrationsApi.listOrchestrationInstances(category),
  });
}

/**
 * 查询单个编排实例组详情
 */
export function useOrchestrationInstanceDetail(instanceId: number | null) {
  return useQuery<OrchestrationInstanceDetail>({
    queryKey: ["orchestration-instances", instanceId, "detail"],
    queryFn: () =>
      orchestrationsApi.getOrchestrationInstanceDetail(instanceId!),
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
    }) => orchestrationsApi.updateOrchestrationInstance(id, data),
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
      orchestrationsApi.deleteOrchestrationInstance(id),
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
    queryFn: () => orchestrationsApi.getImportCandidates(name),
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
    }) => orchestrationsApi.importOrchestration(name, data),
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

/**
 * 验证应用访问地址与认证信息
 */
export function useVerifyAppAuth() {
  const toast = useToast();
  return useMutation({
    mutationFn: (data: AppAuthVerifyRequest) =>
      orchestrationsApi.verifyAppAuth(data),
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
    }) => orchestrationsApi.deployOrchestration(name, data),
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

/**
 * 修复编排实例组（重新部署失败/卡死的应用）
 */
export function useRedeployOrchestrationInstance() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: DeployOrchestrationRequest;
    }) => orchestrationsApi.redeployOrchestrationInstance(id, data),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      qc.invalidateQueries({ queryKey: ["apps", "instances"] });
      qc.invalidateQueries({ queryKey: ["orchestration-instances"] });
      qc.invalidateQueries({
        queryKey: ["orchestration-instances", variables.id, "detail"],
      });
      toast.success("修复已启动");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "修复失败");
    },
  });
}

/**
 * 手动重跑应用间自动装配（后台任务）
 *
 * 装配结果写入实例详情的 app_configs.integrations，这里在启动后
 * 延迟两次刷新详情查询，让装配结果自动出现在界面上。
 */
export function useWireOrchestrationInstance() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (id: number) =>
      orchestrationsApi.wireOrchestrationInstance(id),
    onSuccess: (_data, id) => {
      toast.success("装配已在后台开始，结果稍后自动刷新");
      for (const delay of [4000, 10000]) {
        setTimeout(() => {
          qc.invalidateQueries({
            queryKey: ["orchestration-instances", id, "detail"],
          });
        }, delay);
      }
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "装配启动失败");
    },
  });
}

/**
 * 应用配置健康检测
 *
 * 检测为实时调用后端应用 API、耗时数秒，因此默认不自动执行，
 * 由面板通过 refetch() 手动触发；使用独立顶层 queryKey，避免
 * orchestration-instances 的宽泛失效导致误触发重新检测。
 */
export function useAppInspect(
  instanceId: number | null,
  appName: string | null
) {
  return useQuery<AppInspectReport>({
    queryKey: ["orchestration-inspect", instanceId, appName],
    queryFn: () =>
      orchestrationsApi.inspectOrchestrationApp(instanceId!, appName!),
    enabled: false,
    gcTime: 0,
    retry: false,
  });
}

/**
 * 检测项自动修复，成功后 toast 汇总结果；面板在 onSuccess 中重新检测
 */
export function useFixAppInspect() {
  const toast = useToast();
  return useMutation({
    mutationFn: ({
      instanceId,
      appName,
      itemIds,
    }: {
      instanceId: number;
      appName: string;
      itemIds: string[];
    }) =>
      orchestrationsApi.fixOrchestrationAppInspect(
        instanceId,
        appName,
        itemIds
      ),
    onSuccess: (data) => {
      const okCount = data.results.filter((r) => r.ok).length;
      const failCount = data.results.length - okCount;
      const firstError = data.results.find((r) => !r.ok)?.message;
      if (failCount === 0) {
        toast.success(`修复完成：${okCount} 项全部成功`);
      } else {
        toast.error(
          `修复完成：成功 ${okCount} 项，失败 ${failCount} 项${
            firstError ? `（${firstError}）` : ""
          }`
        );
      }
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "修复失败");
    },
  });
}

/**
 * 查询应用已安装插件与插件市场列表（当前仅 MoviePilot 支持）
 *
 * 接口依赖应用在线且已认证，失败时由面板展示错误提示。
 */
export function useAppPlugins(
  instanceId: number | null,
  appName: string | null
) {
  return useQuery<AppPluginsResponse>({
    queryKey: ["orchestration-app-plugins", instanceId, appName],
    queryFn: () =>
      orchestrationsApi.listOrchestrationAppPlugins(instanceId!, appName!),
    enabled: !!instanceId && !!appName,
    retry: false,
  });
}

/**
 * 安装应用插件（当前仅 MoviePilot 支持）
 */
export function useInstallAppPlugin() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({
      instanceId,
      appName,
      pluginId,
      repoUrl,
    }: {
      instanceId: number;
      appName: string;
      pluginId: string;
      repoUrl?: string;
    }) =>
      orchestrationsApi.installOrchestrationAppPlugin(instanceId, appName, {
        plugin_id: pluginId,
        repo_url: repoUrl,
      }),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({
        queryKey: [
          "orchestration-app-plugins",
          variables.instanceId,
          variables.appName,
        ],
      });
      toast.success("插件安装成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "插件安装失败");
    },
  });
}
