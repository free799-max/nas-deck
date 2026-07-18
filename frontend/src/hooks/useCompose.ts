/**
 * Docker Compose 编排相关 React Query hooks
 *
 * 提供 hooks 用于 Compose 项目管理：
 * - useComposeProjects：查询项目列表
 * - useComposeProject：查询单个项目详情
 * - useCreateComposeProject：创建项目
 * - useUpdateComposeProject：更新项目元数据
 * - useDeleteComposeProject：删除项目
 * - useComposeVersions：查询版本列表
 * - useRollbackComposeVersion：切换版本
 * - useComposeAction：执行 up/down/restart
 * - useComposeLogs：查询日志
 * - useComposeStatus：查询/同步 Stack 状态
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "@/components/ui/toast";
import type { ApiError } from "@/api/types";
import type { ContainerInfo } from "@/api/docker";
import * as composeApi from "@/api/compose";
import type {
  ComposeVersion,
  ComposeStackStatus,
  ComposeProject,
  ComposeProjectCreate,
  ComposeProjectUpdate,
  ComposeEditRequest,
  ComposeActionRequest,
} from "@/api/compose";

// 保持既有导出，页面侧 import 路径无需变更
export type {
  ComposeVersion,
  ComposeStackStatus,
  ComposeProject,
  ComposeProjectCreate,
  ComposeProjectUpdate,
  ComposeEditRequest,
  ComposeActionRequest,
  ComposeDeployTaskResponse,
} from "@/api/compose";

/**
 * 查询 Compose 项目列表
 *
 * 默认 10 秒自动刷新，配合后端实时状态同步。
 */
export function useComposeProjects() {
  return useQuery<ComposeProject[]>({
    queryKey: ["compose", "projects"],
    queryFn: composeApi.listComposeProjects,
    refetchInterval: 10000,
  });
}

/**
 * 查询单个 Compose 项目详情
 */
export function useComposeProject(
  projectId: number | null,
  options?: { refetchInterval?: number | false }
) {
  return useQuery<ComposeProject>({
    queryKey: ["compose", "projects", projectId],
    queryFn: () => composeApi.getComposeProject(projectId!),
    enabled: !!projectId,
    refetchInterval: options?.refetchInterval ?? false,
  });
}

/**
 * 创建 Compose 项目（异步）
 */
export function useCreateComposeProject() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (data: ComposeProjectCreate) =>
      composeApi.createComposeProject(data),
    onSuccess: () => {
      // 刷新项目列表，让新项目及时出现
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      toast.success("创建部署任务已启动");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "创建编排项目失败");
    },
  });
}

/**
 * 更新 Compose 项目元数据
 */
export function useUpdateComposeProject(projectId: number) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (data: ComposeProjectUpdate) =>
      composeApi.updateComposeProject(projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      qc.invalidateQueries({ queryKey: ["compose", "projects", projectId] });
      toast.success("项目信息更新成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "更新项目信息失败");
    },
  });
}

/**
 * 编辑 Compose 项目并自动部署（异步）
 */
export function useEditComposeProject(projectId: number) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (data: ComposeEditRequest) =>
      composeApi.editComposeProject(projectId, data),
    onSuccess: () => {
      // 刷新项目列表与详情（含状态），避免展示旧版本信息
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      qc.invalidateQueries({ queryKey: ["compose", "projects", projectId] });
      toast.success("编辑部署任务已启动");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "保存并部署失败");
    },
  });
}

/**
 * 删除 Compose 项目
 */
export function useDeleteComposeProject() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (projectId: number) =>
      composeApi.deleteComposeProject(projectId),
    onMutate: async (projectId) => {
      await qc.cancelQueries({ queryKey: ["compose", "projects"] });
      const previous = qc.getQueryData<ComposeProject[]>(["compose", "projects"]);
      qc.setQueryData<ComposeProject[]>(
        ["compose", "projects"],
        (old) => old?.filter((p) => p.id !== projectId)
      );
      return { previous };
    },
    onError: (error: ApiError, _projectId: number, context) => {
      if (context?.previous) {
        qc.setQueryData<ComposeProject[]>(["compose", "projects"], context.previous);
      }
      toast.error(error.displayMessage || "删除编排项目失败");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      toast.success("编排项目已删除");
    },
  });
}

/**
 * 查询 Compose 版本列表
 */
export function useComposeVersions(projectId: number | null) {
  return useQuery<ComposeVersion[]>({
    queryKey: ["compose", "projects", projectId, "versions"],
    queryFn: () => composeApi.listComposeVersions(projectId!),
    enabled: !!projectId,
  });
}

/**
 * 切换 Compose 版本
 */
export function useRollbackComposeVersion(projectId: number) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (versionId: number) =>
      composeApi.rollbackComposeVersion(projectId, versionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      qc.invalidateQueries({
        queryKey: ["compose", "projects", projectId, "versions"],
      });
      qc.invalidateQueries({
        queryKey: ["compose", "projects", projectId, "status"],
      });
      toast.success("版本切换成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "版本切换失败");
    },
  });
}

/**
 * 执行 Compose 操作（up/down/restart，异步）
 */
export function useComposeAction() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({
      projectId,
      action,
    }: {
      projectId: number;
      action: ComposeActionRequest["action"];
    }) => composeApi.composeAction(projectId, action),
    onSuccess: (_, { projectId, action }) => {
      // 刷新项目列表与详情（含状态），及时反映 up/down/restart 结果
      qc.invalidateQueries({ queryKey: ["compose", "projects"] });
      qc.invalidateQueries({ queryKey: ["compose", "projects", projectId] });
      const actionMap: Record<string, string> = {
        up: "启动",
        down: "停止",
        restart: "重启",
      };
      toast.success(`${actionMap[action] || action} 任务已启动`);
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "操作失败");
    },
  });
}

/**
 * 查询 Compose 日志
 */
export function useComposeLogs(
  projectId: number | null,
  tail: number = 100,
  services?: string[]
) {
  return useQuery<{ logs: string }>({
    queryKey: ["compose", "projects", projectId, "logs", tail, services],
    queryFn: () => composeApi.getComposeLogs(projectId!, tail, services),
    enabled: !!projectId,
  });
}

// eslint-disable-next-line no-control-regex
const ANSI_PATTERN = /\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g;

function stripAnsi(text: string): string {
  return text.replace(ANSI_PATTERN, "");
}

function cleanLogLine(line: string): string {
  const cleaned = stripAnsi(line).replace(/\r?\n$/, "");
  if (cleaned.includes("\r")) {
    return cleaned.split("\r").pop() ?? cleaned;
  }
  return cleaned;
}

/**
 * 流式获取 Compose 项目日志（SSE）
 *
 * @param projectId 项目 ID
 * @param tail 返回最后 N 行日志
 * @param onError 错误回调，由调用方决定如何展示错误（如 toast 并关闭弹窗）
 * @returns 日志行数组、连接状态、清空函数
 */
export function useComposeLogsStream(
  projectId: number | null,
  tail: number = 100,
  onError?: (message: string) => void
) {
  const [logs, setLogs] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const onErrorRef = useRef(onError);

  // 保持 onError 最新引用，避免其变化导致 SSE 反复重建
  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const clearLogs = useCallback(() => setLogs([]), []);

  useEffect(() => {
    if (!projectId) return;

    const token = localStorage.getItem("token") || "";
    const es = new EventSource(
      `/api/docker/compose/${projectId}/logs/stream?tail=${tail}&follow=true&token=${encodeURIComponent(token)}`
    );

    es.onopen = () => {
      setConnected(true);
      setLogs([]);
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error) {
          onErrorRef.current?.(data.error);
          setConnected(false);
          return;
        }
        if (typeof data.line === "string") {
          setLogs((prev) => [...prev, cleanLogLine(data.line)]);
        }
      } catch {
        // 忽略解析错误
      }
    };

    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
      setLogs([]);
      setConnected(false);
    };
  }, [projectId, tail]);

  return { logs, connected, clearLogs };
}

/**
 * 查询/同步 Compose Stack 状态
 */
export function useComposeStatus(projectId: number | null) {
  return useQuery<ComposeStackStatus>({
    queryKey: ["compose", "projects", projectId, "status"],
    queryFn: () => composeApi.getComposeStatus(projectId!),
    enabled: !!projectId,
    refetchInterval: 30000,
  });
}

/**
 * 查询 Compose 项目维护的容器列表
 *
 * 通过容器标签 nasdeck.compose.project 过滤归属容器。
 */
export function useComposeProjectContainers(projectId: number | null) {
  return useQuery<ContainerInfo[]>({
    queryKey: ["compose", "projects", projectId, "containers"],
    queryFn: () => composeApi.getComposeProjectContainers(projectId!),
    enabled: !!projectId,
    refetchInterval: 10000,
  });
}
