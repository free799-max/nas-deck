/**
 * Docker 拉取任务历史记录工具
 *
 * 通过 localStorage 持久化下载历史，支持：
 * - 记录多个下载任务（进行中、已完成、失败、取消）
 * - 按开始时间降序排列，最新下载在最上方
 * - 非活跃任务（已完成/失败/取消超过 30 分钟）自动清理
 * - 最多保留 10 条历史记录
 */

import type { PullProgressEvent } from "@/hooks/useDocker";

const PULL_HISTORY_KEY = "docker_pull_history";

/** 不活跃超时时间：30 分钟 */
export const INACTIVE_TIMEOUT_MS = 30 * 60 * 1000;

/** 最大保留记录数 */
export const MAX_HISTORY_COUNT = 10;

/** 拉取历史记录项 */
export interface PullHistoryItem {
  /** 任务唯一标识 */
  taskId: string;
  /** 镜像名称（含标签） */
  image: string;
  /** 任务状态 */
  status: "pulling" | "completed" | "failed" | "cancelled";
  /** 任务开始时间戳 */
  createdAt: number;
  /** 任务完成/失败时间戳 */
  completedAt: number | null;
  /** 最后活跃时间戳（收到进度或状态更新） */
  lastActivityAt: number;
  /** 错误信息 */
  error: string | null;
  /** 完成/失败时的最终进度快照 */
  finalProgress: PullProgressEvent | null;
}

/** 按 createdAt 降序排列（最新的在最前面） */
export function sortPullHistory(items: PullHistoryItem[]): PullHistoryItem[] {
  return [...items].sort((a, b) => b.createdAt - a.createdAt);
}

/** 检查记录是否已超时（非 pulling 状态且超过不活跃时间） */
export function isItemInactive(item: PullHistoryItem): boolean {
  if (item.status === "pulling") return false;
  return Date.now() - item.lastActivityAt > INACTIVE_TIMEOUT_MS;
}

/** 清理过期和超限的记录 */
export function cleanupHistory(items: PullHistoryItem[]): PullHistoryItem[] {
  // 先按 createdAt 升序排列，方便移除最旧的
  const sorted = [...items].sort((a, b) => a.createdAt - b.createdAt);
  // 过滤掉不活跃的
  const active = sorted.filter((item) => !isItemInactive(item));
  // 超过上限时移除最旧的
  if (active.length > MAX_HISTORY_COUNT) {
    return active.slice(active.length - MAX_HISTORY_COUNT);
  }
  return active;
}

/** 保存历史记录到 localStorage */
function saveHistory(items: PullHistoryItem[]) {
  localStorage.setItem(PULL_HISTORY_KEY, JSON.stringify(items));
}

/** 获取 localStorage 中的历史记录，自动清理过期/超限记录 */
export function getPullHistory(): PullHistoryItem[] {
  try {
    const raw = localStorage.getItem(PULL_HISTORY_KEY);
    if (!raw) return [];
    const items: PullHistoryItem[] = JSON.parse(raw);
    const cleaned = cleanupHistory(items);
    if (cleaned.length !== items.length) {
      saveHistory(cleaned);
    }
    return sortPullHistory(cleaned);
  } catch {
    return [];
  }
}

/** 添加新的历史记录项 */
export function addPullHistoryItem(taskId: string, image: string) {
  const items = getPullHistory().filter((item) => item.taskId !== taskId);
  items.push({
    taskId,
    image,
    status: "pulling",
    createdAt: Date.now(),
    completedAt: null,
    lastActivityAt: Date.now(),
    error: null,
    finalProgress: null,
  });
  saveHistory(sortPullHistory(items));
}

/** 更新历史记录项 */
export function updatePullHistoryItem(
  taskId: string,
  partial: Partial<Omit<PullHistoryItem, "taskId" | "image" | "createdAt">>
) {
  const items = getPullHistory();
  const index = items.findIndex((item) => item.taskId === taskId);
  if (index === -1) return;

  const item = items[index];
  const updated: PullHistoryItem = {
    ...item,
    ...partial,
    lastActivityAt: Date.now(),
  };

  // 如果状态变为完成/失败/取消，且 completedAt 未设置，则自动设置
  if (
    ["completed", "failed", "cancelled"].includes(updated.status) &&
    updated.completedAt === null
  ) {
    updated.completedAt = Date.now();
  }

  // 短路：终端状态且关键字段未变化时，避免重复写入 localStorage
  const terminalStatuses = ["completed", "failed", "cancelled"];
  const isTerminal = terminalStatuses.includes(item.status);
  const statusUnchanged = updated.status === item.status;
  const errorUnchanged = updated.error === item.error;
  const progressPercentageUnchanged =
    updated.finalProgress?.percentage === item.finalProgress?.percentage;
  if (
    isTerminal &&
    statusUnchanged &&
    errorUnchanged &&
    progressPercentageUnchanged
  ) {
    return;
  }

  items[index] = updated;
  saveHistory(items);
}

/** 移除单条历史记录 */
export function removePullHistoryItem(taskId: string) {
  const items = getPullHistory().filter((item) => item.taskId !== taskId);
  saveHistory(items);
}

/** 清空全部历史记录 */
export function clearPullHistory() {
  localStorage.removeItem(PULL_HISTORY_KEY);
}
