/**
 * 系统设置相关 API
 */

import api from "@/lib/api";

/** 系统全局配置（前端使用空字符串代替 null） */
export interface SystemConfig {
  id: number;
  http_proxy: string;
  https_proxy: string;
  no_proxy: string;
  service_port_start: number;
  default_admin_username: string;
  default_admin_password: string;
}

/** 系统配置更新请求 */
export interface SystemConfigUpdate {
  http_proxy?: string | null;
  https_proxy?: string | null;
  no_proxy?: string | null;
  service_port_start?: number;
  default_admin_username?: string;
  default_admin_password?: string;
}

/** 查询系统全局配置（后端字段可能为 null，统一转为空字符串） */
export function getSystemConfig(): Promise<SystemConfig> {
  return api.get("/settings").then((r) => {
    const data = r.data;
    return {
      ...data,
      http_proxy: data.http_proxy ?? "",
      https_proxy: data.https_proxy ?? "",
      no_proxy: data.no_proxy ?? "",
      service_port_start: data.service_port_start ?? 10000,
      default_admin_username: data.default_admin_username ?? "admin",
      default_admin_password: data.default_admin_password ?? "",
    };
  });
}

/** 更新系统全局配置 */
export function updateSystemConfig(data: SystemConfigUpdate) {
  return api.put("/settings", data).then((r) => r.data);
}

/** 存储目录：宿主机路径 ↔ 容器内路径的对应关系 */
export interface StorageDirectory {
  id: number;
  name: string;
  /** 宿主机路径 */
  host_path: string;
  /** 容器内路径 */
  mount_path: string;
  remark: string | null;
  enabled: boolean;
  /** 是否为应用数据目录（全表至多一条，存放应用配置等持久化小数据） */
  is_app_data: boolean;
  sort_order: number;
  /** mount_path 在后端容器内是否可见 */
  visible: boolean;
  created_at: string;
  updated_at: string;
}

/** 新建存储目录请求 */
export interface StorageDirectoryCreate {
  name: string;
  host_path: string;
  mount_path: string;
  remark?: string | null;
  enabled?: boolean;
  /** 设为应用数据目录；保存为 true 时后端会自动清除其他记录的该标记 */
  is_app_data?: boolean;
  sort_order?: number;
}

/** 更新存储目录请求（部分字段） */
export type StorageDirectoryUpdate = Partial<StorageDirectoryCreate>;

/** 查询存储目录列表 */
export function listStorageDirectories(): Promise<StorageDirectory[]> {
  return api.get("/settings/storage-directories").then((r) => r.data);
}

/** 新建存储目录 */
export function createStorageDirectory(
  data: StorageDirectoryCreate
): Promise<StorageDirectory> {
  return api.post("/settings/storage-directories", data).then((r) => r.data);
}

/** 更新存储目录 */
export function updateStorageDirectory(
  id: number,
  data: StorageDirectoryUpdate
): Promise<StorageDirectory> {
  return api
    .put(`/settings/storage-directories/${id}`, data)
    .then((r) => r.data);
}

/** 删除存储目录 */
export function deleteStorageDirectory(id: number): Promise<null> {
  return api.delete(`/settings/storage-directories/${id}`).then((r) => r.data);
}

/** 获取服务端口分配建议（从起始端口顺序分配的空闲端口） */
export function getPortSuggestions(count: number): Promise<number[]> {
  return api
    .get("/settings/port-suggestions", { params: { count } })
    .then((r) => r.data.ports as number[]);
}
