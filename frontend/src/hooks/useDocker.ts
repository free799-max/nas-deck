/**
 * Docker 相关 React Query hooks
 *
 * 提供 hooks 用于 Docker 管理功能：
 * - useDockerStatus：查询 Docker 服务是否可用
 * - useContainers：查询容器列表
 * - useContainerAction：对容器执行操作（启动/停止/重启等）
 * - useDockerHostInfo：查询 Docker 宿主机综合信息
 *
 * 容器相关查询 hooks 设置了 30 秒自动刷新间隔（refetchInterval: 30000），
 * 以保持容器状态的实时性。
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";

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
 * 检测 Docker 守护进程是否可用，每 30 秒自动刷新。
 *
 * @returns useQuery 对象，data 类型为 { available: boolean }
 */
export function useDockerStatus() {
  return useQuery<{ available: boolean }>({
    queryKey: ["docker", "status"],
    queryFn: () => api.get("/docker/status").then((r) => r.data),
    refetchInterval: 30000,  // 每 30 秒自动刷新 Docker 状态
  });
}

/**
 * 查询容器列表
 *
 * 获取当前用户的所有容器信息，每 30 秒自动刷新。
 *
 * @returns useQuery 对象，data 类型为 ContainerInfo 数组
 */
export function useContainers() {
  return useQuery<ContainerInfo[]>({
    queryKey: ["docker", "containers"],
    queryFn: () => api.get("/docker/containers").then((r) => r.data),
    refetchInterval: 30000,  // 每 30 秒自动刷新容器列表
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
  enable_mirror: boolean;
  username: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建镜像搜索接口配置请求 */
export interface RegistryCreate {
  name: string;
  search_api_url: string;
  mirror_url?: string | null;
  enable_mirror?: boolean;
  username?: string | null;
  password?: string | null;
}

/** 更新镜像搜索接口配置请求 */
export interface RegistryUpdate {
  name?: string;
  search_api_url?: string;
  mirror_url?: string | null;
  enable_mirror?: boolean;
  username?: string | null;
  password?: string | null;
}

/** 批量删除镜像请求 */
export interface BatchImageDeleteRequest {
  ids: string[];
  force?: boolean;
}

/** 本地镜像信息 */
export interface ImageInfo {
  id: string;
  tags: string[];
  size: number;
  created: string;
  containers: number;
}

/** Docker Hub 搜索结果 */
export interface ImageSearchResult {
  name: string;
  description: string;
  star_count: number;
  official: boolean;
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
    refetchInterval: 30000,
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker", "images"] });
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
 * @returns useQuery 对象，data 类型为 ImageSearchResult 数组
 */
export function useSearchImages(q: string) {
  return useQuery<ImageSearchResult[]>({
    queryKey: ["docker", "images", "search", q],
    queryFn: () =>
      api.get("/docker/images/search", { params: { q } }).then((r) => r.data),
    enabled: !!q.trim(),
    staleTime: 60_000,
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
      qc.invalidateQueries({ queryKey: ["docker", "images"] });
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
      qc.invalidateQueries({ queryKey: ["docker", "images"] });
      const deleted = res.data?.deleted?.length || 0;
      const failed = res.data?.failed?.length || 0;
      if (deleted > 0) {
        toast.success(`已删除 ${deleted} 个镜像`);
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
