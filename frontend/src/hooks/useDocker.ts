/**
 * Docker 相关 React Query hooks
 *
 * 提供三个 hooks 用于 Docker 管理功能：
 * - useDockerStatus：查询 Docker 服务是否可用
 * - useContainers：查询容器列表
 * - useContainerAction：对容器执行操作（启动/停止/重启等）
 *
 * 所有查询 hooks 设置了 30 秒自动刷新间隔（refetchInterval: 30000），
 * 以保持容器状态的实时性。
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

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
  return useMutation({
    // 向容器操作接口发送 POST 请求
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api.post(`/docker/containers/${id}/action`, { action }),
    // 操作成功后，使容器列表缓存失效以触发重新查询
    onSuccess: () => qc.invalidateQueries({ queryKey: ["docker", "containers"] }),
  });
}
