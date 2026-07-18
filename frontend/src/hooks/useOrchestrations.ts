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
