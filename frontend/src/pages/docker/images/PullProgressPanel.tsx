/**
 * 镜像拉取进度面板（重构版）
 *
 * 展示当前下载历史记录列表。每个任务显示：
 * - 总进度条 + 百分比 + 下载速度 + 总大小
 * - 每层独立展开显示（层ID + 中文状态 + 进度条 + 大小）
 *
 * 支持页面切换后恢复进度（通过 localStorage 同步历史记录）。
 * 内部使用 PullTaskCard 组件，进度数据由 useAllPullProgress 统一获取。
 */

import { useEffect, useState } from "react";
import { useAllPullProgress } from "@/hooks/useDocker";
import { Badge } from "@/components/ui/badge";
import { PullTaskCard } from "./PullTaskCard";
import {
  getPullHistory,
  removePullHistoryItem,
  type PullHistoryItem,
} from "@/lib/docker-progress";
import { Download } from "lucide-react";

/** 拉取进度面板 */
export function PullProgressPanel() {
  const [history, setHistory] = useState<PullHistoryItem[]>(getPullHistory);

  // 页面可见性变化时重新读取 localStorage（支持跨页面恢复）
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        setHistory(getPullHistory());
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);

  // 监听 localStorage 变化
  useEffect(() => {
    const handleStorage = () => setHistory(getPullHistory());
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const pullingTaskIds = history
    .filter((item) => item.status === "pulling")
    .map((t) => t.taskId);
  const { states: progressStates } = useAllPullProgress(pullingTaskIds);

  if (history.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Download className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-medium">拉取任务</h3>
        <Badge
          variant="outline"
          className="text-[10px] h-4 px-1 bg-primary/10 text-primary border-primary/20"
        >
          {history.length}
        </Badge>
      </div>
      <div className="space-y-2">
        {history.map((task, index) => {
          const s = progressStates[task.taskId];
          return (
            <PullTaskCard
              key={task.taskId}
              image={task.image}
              progress={s?.progress ?? task.finalProgress}
              finalProgress={task.finalProgress}
              status={s?.status ?? task.status}
              error={s?.error ?? task.error}
              createdAt={task.createdAt}
              lastActivityAt={task.lastActivityAt}
              defaultExpanded={index === 0}
              onRemove={() => {
                removePullHistoryItem(task.taskId);
                setHistory(getPullHistory());
                window.dispatchEvent(new Event("storage"));
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
