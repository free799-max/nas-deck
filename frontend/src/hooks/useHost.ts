/**
 * 宿主机相关 React Query hooks
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useToast } from "@/components/ui/toast";

/** API 错误对象 */
interface ApiError {
  displayMessage?: string;
}

/** 目录条目 */
export interface DirectoryEntry {
  name: string;
  path: string;
  is_directory: boolean;
}

/** 目录列表响应 */
export interface DirectoryList {
  path: string;
  entries: DirectoryEntry[];
  exists?: boolean;
}

/** 创建目录请求 */
export interface CreateDirectoryRequest {
  path: string;
  name: string;
}

/** 重命名目录请求 */
export interface RenameDirectoryRequest {
  old_path: string;
  new_name: string;
}

/** 删除目录请求 */
export interface DeleteDirectoryRequest {
  path: string;
}

/**
 * 查询宿主机指定路径下的目录列表
 */
export function useDirectories(path: string, enabled = true) {
  return useQuery<DirectoryList>({
    queryKey: ["host", "directories", path],
    queryFn: () =>
      api
        .get("/docker/host/directories", { params: { path } })
        .then((r) => r.data),
    enabled: enabled && !!path,
    staleTime: 0,
  });
}

/**
 * 创建目录
 */
export function useCreateDirectory() {
  const qc = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (data: CreateDirectoryRequest) =>
      api.post("/docker/host/directories", data).then((r) => r.data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["host", "directories", vars.path] });
      toast.success("创建成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "创建失败");
    },
  });
}

/**
 * 重命名目录
 */
export function useRenameDirectory() {
  const qc = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (data: RenameDirectoryRequest) =>
      api.put("/docker/host/directories", data).then((r) => r.data),
    onSuccess: (_, vars) => {
      const parent = vars.old_path.replace(/\/[^/]*\/?$/, "") || "/";
      qc.invalidateQueries({ queryKey: ["host", "directories", parent] });
      toast.success("重命名成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "重命名失败");
    },
  });
}

/**
 * 删除目录
 */
export function useDeleteDirectory() {
  const qc = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (data: DeleteDirectoryRequest) =>
      api
        .delete("/docker/host/directories", { data })
        .then((r) => r.data),
    onSuccess: (_, vars) => {
      const parent = vars.path.replace(/\/[^/]*\/?$/, "") || "/";
      qc.invalidateQueries({ queryKey: ["host", "directories", parent] });
      toast.success("删除成功");
    },
    onError: (error: ApiError) => {
      toast.error(error.displayMessage || "删除失败");
    },
  });
}
