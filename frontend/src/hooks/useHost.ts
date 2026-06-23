/**
 * 宿主机相关 React Query hooks
 */

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

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
