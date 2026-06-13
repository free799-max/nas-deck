/**
 * Docker 相关 React Query hooks
 *
 * 提供 hooks 用于 Docker 管理功能：
 * - useDockerStatus：查询 Docker 服务是否可用
 * - useContainers：查询容器列表
 * - useContainerAction：对容器执行操作（启动/停止/重启等）
 * - useDockerHostInfo：查询 Docker 宿主机综合信息
 *
 * 查询默认不自动刷新，仅在挂载/手动触发时拉取，避免页面不必要的刷新。
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useRef, useCallback } from "react";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { formatBytes } from "@/lib/utils";
import { updatePullHistoryItem } from "@/lib/docker-progress";

/**
 * 镜像标签信息
 */
export interface ImageTag {
  name: string;
  last_updated: string;
  size: number;
  digest: string;
}

/**
 * 拉取任务响应
 */
export interface PullTaskResponse {
  task_id: string;
  image: string;
  status: string;
}

/**
 * 单层拉取进度
 */
export interface PullProgressLayer {
  id: string;
  status: string;
  status_text: string;
  current: number;
  total: number;
  progress_text: string;
  percentage: number;
  speed: number;
}

/**
 * 拉取进度事件
 */
export interface PullProgressEvent {
  total_layers: number;
  completed_layers: number;
  current_layer: string;
  percentage: number;
  status: string;
  speed: number;
  total_size: number;
  downloaded_size: number;
  size_text: string;
  layers: PullProgressLayer[];
}

/**
 * 拉取任务完整状态
 */
export interface PullTaskStatus {
  task_id: string;
  image: string;
  status: "pulling" | "completed" | "failed";
  progress: PullProgressEvent;
  error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

/**
 * 容器信息接口
 *
 * 描述 Docker 容器的基本信息，包括 ID、名称、状态、健康状态和使用的镜像。
 */
export interface ContainerInfo {
  /** 容器唯一标识 */
  id: string;
  /** 容器名称 */
  name: string;
  /** 容器运行状态（如 running、stopped 等） */
  status: string;
  /** 容器健康状态（如 healthy、unhealthy 等） */
  health: string;
  /** 容器使用的镜像名称 */
  image: string;
}

/** Docker 引擎版本信息 */
export interface DockerVersionInfo {
  version: string;
  api_version: string;
  go_version: string;
  os: string;
  arch: string;
  kernel_version: string;
  build_time: string;
}

/** 宿主机资源信息 */
export interface ResourceInfo {
  cpu_cores: number;
  memory_total: number;
  disk_total: number;
  disk_used: number;
  disk_free: number;
  disk_usage_percent: number;
}

/** Docker 统计信息 */
export interface DockerStatsInfo {
  containers_total: number;
  containers_running: number;
  containers_paused: number;
  containers_stopped: number;
  images: number;
}

/** Docker 网络信息 */
export interface NetworkInfo {
  id: string;
  name: string;
  driver: string;
  scope: string;
}

/** Docker 宿主机综合信息 */
export interface HostInfo {
  hostname: string;
  os: string;
  arch: string;
  kernel_version: string;
  docker_version: DockerVersionInfo;
  resources: ResourceInfo;
  stats: DockerStatsInfo;
  storage_driver: string;
  docker_root_dir: string;
  networks: NetworkInfo[];
}

/**
 * 查询 Docker 服务状态
 *
 * 检测 Docker 守护进程是否可用。
 *
 * @returns useQuery 对象，data 类型为 { available: boolean }
 */
export function useDockerStatus() {
  return useQuery<{ available: boolean }>({
    queryKey: ["docker", "status"],
    queryFn: () => api.get("/docker/status").then((r) => r.data),
  });
}

/**
 * 查询容器列表
 *
 * 获取当前用户的所有容器信息。
 *
 * @returns useQuery 对象，data 类型为 ContainerInfo 数组
 */
export function useContainers() {
  return useQuery<ContainerInfo[]>({
    queryKey: ["docker", "containers"],
    queryFn: () => api.get("/docker/containers").then((r) => r.data),
  });
}

/**
 * 对容器执行操作（mutation）
 *
 * 向后端发送容器操作请求（如启动、停止、重启等），
 * 操作成功后自动刷新容器列表缓存。
 *
 * @returns useMutation 对象，传入参数为 { id: 容器ID, action: 操作类型 }
 */
export function useContainerAction() {
  // 获取 QueryClient 实例，用于手动刷新缓存
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    // 向容器操作接口发送 POST 请求
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api.post(`/docker/containers/${id}/action`, { action }),
    // 操作成功后，使容器列表缓存失效以触发重新查询
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker", "containers"] });
      toast.success("操作成功");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "操作失败");
    },
  });
}

/**
 * 查询 Docker 宿主机综合信息
 *
 * 获取 Docker 宿主机的主机名、操作系统、架构、内核版本、
 * Docker 引擎版本、资源信息、Docker 统计信息和网络列表。
 * 静态展示，不设置自动刷新。
 *
 * @returns useQuery 对象，data 类型为 HostInfo
 */
export function useDockerHostInfo() {
  return useQuery<HostInfo>({
    queryKey: ["docker", "host", "info"],
    queryFn: () => api.get("/docker/host/info").then((r) => r.data),
  });
}

/* ===================== 镜像管理 ===================== */

/** 镜像搜索接口配置 */
export interface Registry {
  id: number;
  name: string;
  search_api_url: string;
  mirror_url: string | null;
  mirror_urls: string[] | null;
  enable_mirror: boolean;
  username: string | null;
  trust_ssl_self_signed: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建镜像搜索接口配置请求 */
export interface RegistryCreate {
  name: string;
  search_api_url: string;
  mirror_url?: string | null;
  mirror_urls?: string[] | null;
  enable_mirror?: boolean;
  username?: string | null;
  password?: string | null;
  trust_ssl_self_signed?: boolean;
}

/** 更新镜像搜索接口配置请求 */
export interface RegistryUpdate {
  name?: string;
  search_api_url?: string;
  mirror_url?: string | null;
  mirror_urls?: string[] | null;
  enable_mirror?: boolean;
  username?: string | null;
  password?: string | null;
  trust_ssl_self_signed?: boolean;
}

/** 批量删除镜像请求 */
export interface BatchImageDeleteRequest {
  ids: string[];
  force?: boolean;
}

/** 本地镜像信息（扁平化，每行对应一个 tag） */
export interface ImageInfo {
  id: string;
  image_id: string;
  name: string;
  tag: string;
  full_tag: string;
  size: number;
  created: string;
  containers: number;
}

/** 镜像层表格数据 */
export interface ImageLayer {
  order: number;
  size: number;
  layer: string;
}

/** 镜像完整元数据 */
export interface ImageDetail {
  id: string;
  name: string;
  tag: string;
  full_tag: string;
  size: number;
  created: string;
  architecture: string;
  os: string;
  cmd: string[] | null;
  entrypoint: string[] | null;
  env: string[] | null;
  exposed_ports: string[] | null;
  volumes: string[] | null;
  working_dir: string | null;
  user: string | null;
  labels: Record<string, string> | null;
  layers: string[] | null;
  history: string[] | null;
  parent: string | null;
  docker_version: string | null;
  build: string | null;
  layers_table: ImageLayer[] | null;
}

/** 移除未使用镜像结果 */
export interface ImagePruneResult {
  deleted: string[];
  space_reclaimed: number;
}

/** Docker Hub 搜索结果 */
export interface ImageSearchResult {
  name: string;
  description: string;
  star_count: number;
  pull_count: number;
  official: boolean;
  is_automated: boolean;
}

/** 镜像搜索分页结果 */
export interface ImageSearchPage {
  total: number;
  page: number;
  page_size: number;
  results: ImageSearchResult[];
}

/**
 * 查询本地镜像列表
 *
 * @returns useQuery 对象，data 类型为 ImageInfo 数组
 */
export function useImages() {
  return useQuery<ImageInfo[]>({
    queryKey: ["docker", "images"],
    queryFn: () => api.get("/docker/images").then((r) => r.data),
  });
}

/**
 * 删除本地镜像（mutation）
 *
 * @returns useMutation 对象
 */
export function useRemoveImage() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) =>
      api.delete(`/docker/images/${id}`, { params: { force } }),
    onSuccess: (_, { id }) => {
      qc.setQueryData<ImageInfo[]>(["docker", "images"], (old) =>
        old?.filter((img) => img.image_id !== id) ?? []
      );
      qc.invalidateQueries({ queryKey: ["docker", "images"], exact: true });
      toast.success("镜像已删除");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "删除失败");
    },
  });
}

/**
 * 从 Docker Hub 搜索镜像
 *
 * @param q 搜索关键词
 * @param page 页码，从 1 开始
 * @returns useQuery 对象，data 类型为 ImageSearchPage
 */
export function useSearchImages(q: string, page: number = 1) {
  return useQuery<ImageSearchPage>({
    queryKey: ["docker", "images", "search", q, page],
    queryFn: () =>
      api
        .get("/docker/images/search", { params: { q, page } })
        .then((r) => r.data),
    enabled: !!q.trim(),
    staleTime: 60_000,
    placeholderData: (previousData) => previousData,
  });
}

/**
 * 拉取镜像（mutation）
 *
 * @returns useMutation 对象
 */
export function usePullImage() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (image: string) => api.post("/docker/images/pull", { image }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker", "images"], exact: true });
      toast.success("镜像拉取成功");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "拉取失败");
    },
  });
}

/**
 * 查询镜像搜索接口配置列表
 *
 * @returns useQuery 对象，data 类型为 Registry 数组
 */
export function useRegistries() {
  return useQuery<Registry[]>({
    queryKey: ["docker", "registries"],
    queryFn: () => api.get("/docker/registries").then((r) => r.data),
  });
}

/**
 * 创建镜像搜索接口配置（mutation）
 *
 * @returns useMutation 对象
 */
export function useCreateRegistry() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (data: RegistryCreate) => api.post("/docker/registries", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker", "registries"] });
      toast.success("配置已创建");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "创建失败");
    },
  });
}

/**
 * 更新镜像搜索接口配置（mutation）
 *
 * @returns useMutation 对象
 */
export function useUpdateRegistry() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: RegistryUpdate }) =>
      api.put(`/docker/registries/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker", "registries"] });
      toast.success("配置已更新");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "更新失败");
    },
  });
}

/**
 * 删除镜像搜索接口配置（mutation）
 *
 * @returns useMutation 对象
 */
export function useDeleteRegistry() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/docker/registries/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker", "registries"] });
      toast.success("配置已删除");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "删除失败");
    },
  });
}

/**
 * 设置默认镜像搜索接口配置（mutation）
 *
 * @returns useMutation 对象
 */
export function useSetDefaultRegistry() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (id: number) =>
      api.post(`/docker/registries/${id}/set-default`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker", "registries"] });
      toast.success("默认配置已切换");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "切换失败");
    },
  });
}

/**
 * 批量删除本地镜像（mutation）
 *
 * @returns useMutation 对象，传入参数为 BatchImageDeleteRequest
 */
export function useBatchRemoveImages() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (data: BatchImageDeleteRequest) =>
      api.post("/docker/images/batch-delete", data),
    onSuccess: (res: any) => {
      const deletedTags: string[] = res.data?.deleted || [];
      qc.setQueryData<ImageInfo[]>(["docker", "images"], (old) =>
        old?.filter((img) => !deletedTags.includes(img.full_tag)) ?? []
      );
      qc.invalidateQueries({ queryKey: ["docker", "images"], exact: true });
      const failed = res.data?.failed?.length || 0;
      if (deletedTags.length > 0) {
        toast.success(`已删除 ${deletedTags.length} 个镜像`);
      }
      if (failed > 0) {
        toast.error(`${failed} 个镜像删除失败`);
      }
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "批量删除失败");
    },
  });
}

/**
 * 查询镜像完整元数据
 *
 * @param image_id 镜像完整 ID
 * @returns useQuery 对象，data 类型为 ImageDetail
 */
export function useImageDetail(image_id: string | null) {
  return useQuery<ImageDetail>({
    queryKey: ["docker", "images", "detail", image_id],
    queryFn: () =>
      api.get(`/docker/images/${image_id}/detail`).then((r) => r.data),
    enabled: !!image_id,
  });
}

/**
 * 查询指定镜像的可用标签列表
 *
 * @param image 镜像名称（不含标签）
 * @returns useQuery 对象，data 类型为 ImageTag 数组
 */
export function useImageTags(image: string) {
  return useQuery<ImageTag[]>({
    queryKey: ["docker", "images", "tags", image],
    queryFn: () =>
      api
        .get("/docker/images/tags", { params: { image } })
        .then((r) => r.data),
    enabled: !!image.trim(),
    staleTime: 60_000,
  });
}

/**
 * 启动镜像拉取任务（mutation）
 *
 * 返回 task_id，用于后续进度跟踪。
 *
 * @returns useMutation 对象，传入参数为镜像名称（含标签）
 */
export function usePullImageStream() {
  const toast = useToast();
  return useMutation({
    mutationFn: (image: string) =>
      api
        .post<PullTaskResponse>("/docker/images/pull", { image })
        .then((r) => r.data),
    onError: (error: unknown) => {
      const err = error as { displayMessage?: string };
      toast.error(err.displayMessage || "启动拉取失败");
    },
  });
}

/**
 * 多任务拉取进度 Hook
 *
 * 同时管理多个任务的 SSE 连接，返回每个任务的进度状态映射。
 * 支持乐观初始化（任务添加后立即显示 0%）、自动重连（最多 5 次）。
 *
 * @param taskIds 任务 ID 数组
 * @returns 每个任务的状态映射 { [taskId]: { progress, status, error, connected } }
 */
export function useAllPullProgress(taskIds: string[]) {
  const [states, setStates] = useState<
    Record<
      string,
      {
        progress: PullProgressEvent | null;
        status: "pulling" | "completed" | "failed" | null;
        error: string | null;
        connected: boolean;
      }
    >
  >({});

  const toast = useToast();
  const qc = useQueryClient();
  // 用 ref 存储 toast/qc，避免它们引用变化导致 effect 频繁重建
  const toastRef = useRef(toast);
  const qcRef = useRef(qc);
  useEffect(() => {
    toastRef.current = toast;
    qcRef.current = qc;
  }, [toast, qc]);

  const toastedRef = useRef<Set<string>>(new Set());
  const esMapRef = useRef<Record<string, EventSource>>({});
  const reconnectCountRef = useRef<Record<string, number>>({});
  const mountedRef = useRef(true);

  // 管理多个 SSE 连接（增量更新，不重复关闭已有连接）
  useEffect(() => {
    mountedRef.current = true;
    const currentIds = new Set(taskIds);
    const esMap = esMapRef.current;

    // 关闭不再需要的连接
    Object.keys(esMap).forEach((id) => {
      if (!currentIds.has(id)) {
        esMap[id].close();
        delete esMap[id];
        delete reconnectCountRef.current[id];
      }
    });

    taskIds.forEach((taskId) => {
      if (esMap[taskId]) return; // 已有连接，跳过

      // 乐观初始化：任务添加后立即显示准备中状态（已有状态则跳过，防止覆盖 SSE 推送的进度）
      setStates((prev) => {
        if (prev[taskId]) return prev;
        return {
          ...prev,
          [taskId]: {
            progress: {
              total_layers: 0,
              completed_layers: 0,
              current_layer: "",
              percentage: 0,
              status: "准备拉取",
              speed: 0,
              total_size: 0,
              downloaded_size: 0,
              size_text: "--",
              layers: [],
            },
            status: "pulling",
            error: null,
            connected: true,
          },
        };
      });

      const tryConnect = () => {
        reconnectCountRef.current[taskId] =
          (reconnectCountRef.current[taskId] || 0) + 1;

        const token = localStorage.getItem("token");
        const es = new EventSource(
          `/api/docker/images/pull/${taskId}/events?token=${token || ""}`
        );
        esMap[taskId] = es;

        es.onmessage = (event) => {
          try {
            const raw = JSON.parse(event.data);
            const data = raw as PullProgressEvent;
            // 后端在任务完成/失败时嵌入 _task_status 和 _error
            const taskStatus = (raw as Record<string, unknown>)._task_status as
              | "completed"
              | "failed"
              | undefined;
            const taskError = (raw as Record<string, unknown>)._error as
              | string
              | undefined;
            if (!mountedRef.current) return;
            setStates((prev) => ({
              ...prev,
              [taskId]: {
                ...prev[taskId],
                progress: data,
                status: taskStatus || prev[taskId]?.status,
                error: taskError ?? prev[taskId]?.error,
              },
            }));

            // 任务完成或失败时同步更新历史记录状态
            if (taskStatus === "completed" || taskStatus === "failed") {
              updatePullHistoryItem(taskId, {
                status: taskStatus,
                error: taskError || null,
                finalProgress: data,
              });
            }
          } catch {
            // 忽略解析错误
          }
        };

        es.onerror = () => {
          es.close();
          delete esMap[taskId];
          if (!mountedRef.current) return;
          setStates((prev) => ({
            ...prev,
            [taskId]: { ...prev[taskId], connected: false },
          }));

          // 自动重连（最多 5 次，间隔 2 秒）
          if ((reconnectCountRef.current[taskId] || 0) < 5) {
            setTimeout(() => {
              if (!mountedRef.current) return;
              if (esMapRef.current[taskId]) return;
              tryConnect();
            }, 2000);
          }
        };
      };

      tryConnect();

      // 通过 REST API 获取当前状态（保底 + 恢复）
      api
        .get<PullTaskStatus>(`/docker/images/pull/${taskId}/status`)
        .then((r) => {
          if (!mountedRef.current) return;
          const task = r.data;

          setStates((prev) => {
            const existing = prev[taskId];
            // 优化：如果已有 SSE 推送的有效进度，优先保留，防止 REST 旧数据覆盖
            if (
              existing?.progress &&
              existing.progress.percentage > 0 &&
              task.status === "pulling"
            ) {
              return {
                ...prev,
                [taskId]: {
                  ...existing,
                  status: task.status,
                  error: task.error,
                  connected: true,
                },
              };
            }
            return {
              ...prev,
              [taskId]: {
                progress: task.progress,
                status: task.status,
                error: task.error,
                connected: true,
              },
            };
          });

          if (task.status === "completed") {
            updatePullHistoryItem(taskId, {
              status: "completed",
              error: task.error,
              finalProgress: task.progress,
            });
            if (!toastedRef.current.has(taskId)) {
              toastedRef.current.add(taskId);
              toastRef.current.success(`镜像 ${task.image} 拉取完成`);
              qcRef.current.invalidateQueries({
                queryKey: ["docker", "images"],
                exact: true,
              });
            }
            if (esMap[taskId]) {
              esMap[taskId].close();
              delete esMap[taskId];
            }
          } else if (task.status === "failed") {
            updatePullHistoryItem(taskId, {
              status: "failed",
              error: task.error,
              finalProgress: task.progress,
            });
            if (!toastedRef.current.has(taskId)) {
              toastedRef.current.add(taskId);
              toastRef.current.error(task.error || "拉取失败");
            }
            if (esMap[taskId]) {
              esMap[taskId].close();
              delete esMap[taskId];
            }
          }
        })
        .catch(() => {
          // 状态接口失败不影响 SSE
        });
    });

    // 只标记卸载状态，不关闭连接（由下方独立 effect 在组件卸载时清理）
    return () => {
      mountedRef.current = false;
    };
  }, [taskIds.join(",")]);

  // 组件卸载时统一清理所有连接
  useEffect(() => {
    return () => {
      Object.values(esMapRef.current).forEach((es) => es.close());
      esMapRef.current = {};
      reconnectCountRef.current = {};
    };
  }, []);

  // 前端超时检测：每个 pulling 任务 10 分钟后自动标记失败（保留历史记录）
  useEffect(() => {
    const timers = taskIds.map((taskId) =>
      setTimeout(() => {
        setStates((prev) => {
          if (prev[taskId]?.status === "pulling") {
            const finalProgress = prev[taskId]?.progress ?? null;
            updatePullHistoryItem(taskId, {
              status: "failed",
              error: "拉取超时，请检查网络或镜像源配置",
              finalProgress,
            });
            return {
              ...prev,
              [taskId]: {
                ...prev[taskId],
                status: "failed",
                error: "拉取超时，请检查网络或镜像源配置",
                connected: false,
              },
            };
          }
          return prev;
        });
      }, 10 * 60 * 1000)
    );
    return () => timers.forEach(clearTimeout);
  }, [taskIds.join(",")]);

  /** 手动重连（全部或指定任务） */
  const reconnect = useCallback((targetTaskId?: string) => {
    if (targetTaskId) {
      if (esMapRef.current[targetTaskId]) {
        esMapRef.current[targetTaskId].close();
        delete esMapRef.current[targetTaskId];
      }
      delete reconnectCountRef.current[targetTaskId];
    } else {
      Object.values(esMapRef.current).forEach((es) => es.close());
      Object.keys(esMapRef.current).forEach((k) => delete esMapRef.current[k]);
      reconnectCountRef.current = {};
    }
    // 触发状态更新以重新执行 effect
    setStates((prev) => ({ ...prev }));
  }, []);

  return { states, reconnect };
}

/**
 * 单任务拉取进度 Hook
 *
 * 基于 useAllPullProgress 实现，复用多任务 SSE 管理逻辑。
 * 适用于只需要跟踪单个任务进度的场景。
 *
 * @param taskId 任务 ID
 * @returns 进度状态和连接状态
 */
export function usePullProgress(taskId: string | null) {
  const { states, reconnect } = useAllPullProgress(taskId ? [taskId] : []);
  const state = taskId ? states[taskId] : undefined;

  return {
    progress: state?.progress ?? null,
    status: state?.error ? "failed" : state?.status ?? null,
    error: state?.error ?? null,
    connected: state?.connected ?? false,
    reconnect: () => taskId && reconnect(taskId),
  };
}

/**
 * 移除未使用镜像（mutation）
 *
 * @returns useMutation 对象
 */
export function usePruneImages() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: () => api.post("/docker/images/prune"),
    onSuccess: (res: any) => {
      const deletedTags: string[] = res.data?.deleted || [];
      qc.setQueryData<ImageInfo[]>(["docker", "images"], (old) =>
        old?.filter((img) => !deletedTags.includes(img.full_tag)) ?? []
      );
      qc.invalidateQueries({ queryKey: ["docker", "images"], exact: true });
      const space = res.data?.space_reclaimed || 0;
      if (deletedTags.length > 0) {
        toast.success(`已清理 ${deletedTags.length} 个未使用镜像，释放 ${formatBytes(space)}`);
      } else {
        toast.success("没有可清理的未使用镜像");
      }
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "清理失败");
    },
  });
}
