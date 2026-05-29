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
