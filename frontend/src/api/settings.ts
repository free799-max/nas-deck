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
  storage_host_root_dir: string;
  storage_docker_mount_dir: string;
}

/** 系统配置更新请求 */
export interface SystemConfigUpdate {
  http_proxy?: string | null;
  https_proxy?: string | null;
  no_proxy?: string | null;
  storage_host_root_dir?: string | null;
  storage_docker_mount_dir?: string | null;
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
      storage_host_root_dir: data.storage_host_root_dir ?? "",
      storage_docker_mount_dir: data.storage_docker_mount_dir ?? "",
    };
  });
}

/** 更新系统全局配置 */
export function updateSystemConfig(data: SystemConfigUpdate) {
  return api.put("/settings", data).then((r) => r.data);
}
