/**
 * 订阅相关 React Query hooks
 *
 * 提供三个 hooks 用于订阅管理功能：
 * - useSubscriptions：查询当前用户的所有订阅
 * - useCreateSubscription：创建新的订阅
 * - useDeleteSubscription：删除指定的订阅
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";

/**
 * 订阅信息接口
 *
 * 描述一条订阅记录，包含关联的插件实例、订阅目标信息和状态。
 */
export interface Subscription {
  /** 订阅唯一标识 */
  id: number;
  /** 所属用户 ID */
  user_id: number;
  /** 关联的插件实例 ID */
  instance_id: number;
  /** 订阅目标项目的唯一标识（如视频 ID、文章 URL 等） */
  item_id: string;
  /** 订阅目标项目的标题 */
  item_title: string;
  /** 订阅目标项目的元数据（JSON 对象，内容因插件而异） */
  item_meta: Record<string, unknown>;
  /** 订阅状态（如 active、paused、completed 等） */
  status: string;
  /** 上次检查时间（ISO 8601 格式），若从未检查则为 null */
  last_checked: string | null;
  /** 创建时间（ISO 8601 格式） */
  created_at: string;
}

/**
 * 查询当前用户的订阅列表
 *
 * 获取当前用户的所有订阅记录及其状态信息。
 *
 * @returns useQuery 对象，data 类型为 Subscription 数组
 */
export function useSubscriptions() {
  return useQuery<Subscription[]>({
    queryKey: ["subscriptions"],
    queryFn: () => api.get("/subscriptions").then((r) => r.data),
  });
}

/**
 * 创建新的订阅（mutation）
 *
 * 提交订阅信息，创建成功后自动刷新订阅列表缓存。
 *
 * @returns useMutation 对象，传入参数包含 instance_id（插件实例 ID）、item_id（项目标识）、item_title（项目标题）、item_meta（项目元数据）
 */
export function useCreateSubscription() {
  // 获取 QueryClient 实例，用于手动刷新缓存
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    // 向订阅创建接口发送 POST 请求
    mutationFn: (data: {
      instance_id: number;
      item_id: string;
      item_title: string;
      item_meta: Record<string, unknown>;
    }) => api.post("/subscriptions", data),
    // 创建成功后，使订阅列表缓存失效以触发重新查询
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      toast.success("订阅成功");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "订阅失败");
    },
  });
}

/**
 * 删除指定的订阅（mutation）
 *
 * 根据订阅 ID 删除对应的订阅记录，删除成功后自动刷新订阅列表缓存。
 *
 * @returns useMutation 对象，传入参数为订阅 ID
 */
export function useDeleteSubscription() {
  // 获取 QueryClient 实例，用于手动刷新缓存
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    // 向订阅删除接口发送 DELETE 请求
    mutationFn: (id: number) => api.delete(`/subscriptions/${id}`),
    // 删除成功后，使订阅列表缓存失效以触发重新查询
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      toast.success("取消订阅成功");
    },
    onError: (error: any) => {
      toast.error(error.displayMessage || "取消订阅失败");
    },
  });
}
