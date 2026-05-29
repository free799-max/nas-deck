/**
 * 插件相关 React Query hooks
 *
 * 提供四个 hooks 用于插件管理功能：
 * - useAvailablePlugins：查询系统中所有可用的插件
 * - usePluginInstances：查询当前用户已创建的插件实例
 * - useCreateInstance：创建新的插件实例
 * - useDeleteInstance：删除指定的插件实例
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";

/**
 * 插件信息接口
 *
 * 描述一个可用的插件，包含名称、版本、描述和配置 schema。
 */
export interface PluginInfo {
  /** 插件唯一标识名称 */
  name: string;
  /** 插件显示名称（用户可见） */
  display_name: string;
  /** 插件版本号 */
  version: string;
  /** 插件功能描述 */
  description: string;
  /** 插件配置 schema（JSON Schema 格式，用于前端动态表单） */
  config_schema: Record<string, unknown>;
}

/**
 * 插件实例接口
 *
 * 描述一个已创建的插件实例，包含配置信息和运行状态。
 */
export interface PluginInstance {
  /** 实例唯一标识 */
  id: number;
  /** 所属插件的名称 */
  plugin_name: string;
  /** 实例显示名称（用户自定义） */
  display_name: string;
  /** 实例配置（JSON 对象，内容因插件而异） */
  config: Record<string, unknown>;
  /** 关联的 Docker 容器 ID，若未运行则为 null */
  docker_id: string | null;
  /** 是否启用该实例 */
  enabled: boolean;
}

/**
 * 查询可用的插件列表
 *
 * 获取系统中所有已注册的插件及其配置 schema。
 *
 * @returns useQuery 对象，data 类型为 PluginInfo 数组
 */
export function useAvailablePlugins() {
  return useQuery<PluginInfo[]>({
    queryKey: ["plugins", "available"],
    queryFn: () => api.get("/plugins/available").then((r) => r.data),
  });
}

/**
 * 查询已创建的插件实例列表
 *
 * 获取当前用户的所有插件实例及其运行状态。
 *
 * @returns useQuery 对象，data 类型为 PluginInstance 数组
 */
export function usePluginInstances() {
  return useQuery<PluginInstance[]>({
    queryKey: ["plugins", "instances"],
    queryFn: () => api.get("/plugins/instances").then((r) => r.data),
  });
}

/**
 * 创建新的插件实例（mutation）
 *
 * 提交实例的配置信息，创建成功后自动刷新实例列表缓存。
 *
 * @returns useMutation 对象，传入参数包含 plugin_name（插件名称）、display_name（显示名称）、config（配置）
 */
export function useCreateInstance() {
  // 获取 QueryClient 实例，用于手动刷新缓存
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    // 向实例创建接口发送 POST 请求
    mutationFn: (data: {
      plugin_name: string;
      display_name: string;
      config: Record<string, unknown>;
    }) => api.post("/plugins/instances", data),
    // 创建成功后，使实例列表缓存失效以触发重新查询
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plugins", "instances"] });
      toast.success("创建成功");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "创建失败");
    },
  });
}

/**
 * 删除指定的插件实例（mutation）
 *
 * 根据实例 ID 删除对应的插件实例，删除成功后自动刷新实例列表缓存。
 *
 * @returns useMutation 对象，传入参数为实例 ID
 */
export function useDeleteInstance() {
  // 获取 QueryClient 实例，用于手动刷新缓存
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    // 向实例删除接口发送 DELETE 请求
    mutationFn: (id: number) => api.delete(`/plugins/instances/${id}`),
    // 删除成功后，使实例列表缓存失效以触发重新查询
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plugins", "instances"] });
      toast.success("删除成功");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "删除失败");
    },
  });
}
