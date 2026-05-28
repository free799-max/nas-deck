/**
 * 通知相关 React Query hooks
 *
 * 提供五个 hooks 用于通知管理功能：
 * - useNotifiers：查询可用的通知器类型列表
 * - useChannels：查询已配置的通知渠道列表
 * - useCreateChannel：创建新的通知渠道
 * - useDeleteChannel：删除指定通知渠道
 * - useTestNotifier：测试通知器是否能正常发送
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

/**
 * 通知渠道接口
 *
 * 描述一个已配置的通知渠道，包括渠道类型、配置信息和启用状态。
 */
export interface NotificationChannel {
  /** 渠道唯一标识 */
  id: number;
  /** 所属用户 ID */
  user_id: number;
  /** 渠道类型（如 email、webhook、telegram 等） */
  type: string;
  /** 渠道配置（JSON 对象，内容因类型而异） */
  config: Record<string, unknown>;
  /** 是否启用该渠道 */
  enabled: boolean;
}

/**
 * 通知器信息接口
 *
 * 描述一个可用的通知器插件，包含名称和配置 schema。
 */
export interface NotifierInfo {
  /** 通知器名称（唯一标识） */
  name: string;
  /** 通知器的配置 schema（JSON Schema 格式，用于前端动态表单） */
  config_schema: Record<string, unknown>;
}

/**
 * 查询可用的通知器类型列表
 *
 * 获取系统中所有可用的通知器插件及其配置 schema。
 *
 * @returns useQuery 对象，data 类型为 NotifierInfo 数组
 */
export function useNotifiers() {
  return useQuery<NotifierInfo[]>({
    queryKey: ["notifications", "notifiers"],
    queryFn: () => api.get("/notifications/notifiers").then((r) => r.data),
  });
}

/**
 * 查询已配置的通知渠道列表
 *
 * 获取当前用户的所有通知渠道配置。
 *
 * @returns useQuery 对象，data 类型为 NotificationChannel 数组
 */
export function useChannels() {
  return useQuery<NotificationChannel[]>({
    queryKey: ["notifications", "channels"],
    queryFn: () => api.get("/notifications/channels").then((r) => r.data),
  });
}

/**
 * 创建新的通知渠道（mutation）
 *
 * 提交新渠道的配置信息，创建成功后自动刷新渠道列表缓存。
 *
 * @returns useMutation 对象，传入参数包含 type（渠道类型）、config（配置）、enabled（是否启用）
 */
export function useCreateChannel() {
  // 获取 QueryClient 实例，用于手动刷新缓存
  const qc = useQueryClient();
  return useMutation({
    // 向渠道创建接口发送 POST 请求
    mutationFn: (data: { type: string; config: Record<string, unknown>; enabled: boolean }) =>
      api.post("/notifications/channels", data),
    // 创建成功后，使渠道列表缓存失效以触发重新查询
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications", "channels"] }),
  });
}

/**
 * 删除指定通知渠道（mutation）
 *
 * 根据渠道 ID 删除对应的通知渠道，删除成功后自动刷新渠道列表缓存。
 *
 * @returns useMutation 对象，传入参数为渠道 ID
 */
export function useDeleteChannel() {
  // 获取 QueryClient 实例，用于手动刷新缓存
  const qc = useQueryClient();
  return useMutation({
    // 向渠道删除接口发送 DELETE 请求
    mutationFn: (id: number) => api.delete(`/notifications/channels/${id}`),
    // 删除成功后，使渠道列表缓存失效以触发重新查询
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications", "channels"] }),
  });
}

/**
 * 测试通知器发送能力（mutation）
 *
 * 使用指定通知器类型和配置发送一条测试通知，
 * 用于验证渠道配置是否正确。
 *
 * @returns useMutation 对象，传入参数包含 type（通知器类型）和 config（配置）
 */
export function useTestNotifier() {
  return useMutation({
    // 向测试接口发送 POST 请求
    mutationFn: (data: { type: string; config: Record<string, unknown> }) =>
      api.post("/notifications/test", data).then((r) => r.data),
  });
}
