/**
 * 部署任务进度面板
 *
 * 以类终端形式展示一个或多个部署任务的实时进度，
 * 包含阶段徽章、进度条、累计日志流和错误信息。
 */

import { useEffect, useMemo, useRef } from "react";
import {
  useDeployTasksEvents,
  type DeployTaskState,
} from "@/hooks/useDeployTasks";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, Loader2, Terminal } from "lucide-react";

interface DeployProgressPanelProps {
  taskIds: string[];
  onComplete?: (taskId: string, state: DeployTaskState) => void;
  onError?: (taskId: string, state: DeployTaskState) => void;
}

const stageMap: Record<string, string> = {
  preparing: "准备中",
  creating_project: "创建项目",
  writing_compose: "写入配置",
  pulling_images: "拉取镜像",
  preparing_packages: "准备依赖",
  starting_services: "启动服务",
  syncing_status: "同步状态",
  completed: "部署完成",
  failed: "部署失败",
};

const statusVariantMap: Record<
  string,
  { variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  deploying: { variant: "outline", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  completed: { variant: "default", icon: <CheckCircle2 className="h-3 w-3" /> },
  failed: { variant: "destructive", icon: <XCircle className="h-3 w-3" /> },
};

function TaskTitle({ state }: { state: DeployTaskState }) {
  const meta = state.meta || {};
  const title =
    (meta.app_name as string) ||
    (meta.project_name as string) ||
    (meta.instance_name as string) ||
    "部署任务";
  const subtitleCandidates = [
    meta.instance_name as string | undefined,
    meta.description as string | undefined,
    state.taskId.slice(0, 8),
  ];
  const subtitle = subtitleCandidates.find((s) => s && s !== title) ?? state.taskId.slice(0, 8);

  return (
    <div className="min-w-0">
      <p className="text-sm font-semibold truncate">{title}</p>
      <p className="text-xs text-muted-foreground truncate">{subtitle}</p>
    </div>
  );
}

function LogTerminal({ logs, isFailed }: { logs: string[]; isFailed: boolean }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [logs.length]);

  return (
    <div
      className={cn(
        "mt-3 rounded-md border bg-slate-950 text-slate-100 p-3 font-mono text-[11px] leading-snug overflow-y-auto max-h-64 min-h-[120px]",
        isFailed && "border-destructive/50"
      )}
    >
      {logs.length === 0 ? (
        <span className="text-slate-500">等待日志输出…</span>
      ) : (
        logs.map((line, idx) => {
          const isStageLine = line.startsWith("[");
          const isErrorLine = /error|fail/i.test(line);
          return (
            <div
              key={idx}
              className={cn(
                "whitespace-pre-wrap break-words",
                isErrorLine && "text-red-400",
                !isErrorLine && (isStageLine ? "text-slate-100" : "text-slate-300")
              )}
            >
              {line}
            </div>
          );
        })
      )}
      <div ref={bottomRef} />
    </div>
  );
}

function DeployTaskCard({ state, logs }: { state: DeployTaskState; logs: string[] }) {
  const isCompleted = state.status === "completed";
  const isFailed = state.status === "failed";
  const statusConfig = statusVariantMap[state.status] || statusVariantMap.deploying;

  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-4 shadow-sm",
        isFailed && "border-destructive/50 bg-destructive/5"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <TaskTitle state={state} />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant={statusConfig.variant} className="text-[10px] h-5 px-1.5 gap-1">
            {statusConfig.icon}
            {stageMap[state.stage] || state.stage}
          </Badge>
          <span className="text-xs text-muted-foreground w-9 text-right">
            {state.progress.percentage}%
          </span>
        </div>
      </div>

      <div className="mt-3">
        <Progress
          value={state.progress.percentage}
          className={cn(
            "h-1.5",
            isCompleted && "[&_>div]:bg-green-500",
            isFailed && "[&_>div]:bg-destructive"
          )}
        />
      </div>

      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <Terminal className="h-3.5 w-3.5" />
        <span className="truncate">{state.progress.message}</span>
      </div>

      <LogTerminal logs={logs} isFailed={isFailed} />

      {state.error && (
        <div className="mt-3 rounded-md bg-destructive/10 border border-destructive/20 p-3">
          <p className="text-xs font-semibold text-destructive mb-1">部署失败</p>
          <p className="text-xs text-destructive/90 whitespace-pre-wrap break-all">
            {state.error}
          </p>
        </div>
      )}
    </div>
  );
}

/** 部署进度面板 */
export function DeployProgressPanel({
  taskIds,
  onComplete,
  onError,
}: DeployProgressPanelProps) {
  const activeTaskIds = useMemo(() => taskIds.filter(Boolean), [taskIds]);
  const states = useDeployTasksEvents(activeTaskIds, onComplete, onError);

  if (activeTaskIds.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {activeTaskIds.map((taskId) => {
        const state = states[taskId];
        if (!state) {
          return (
            <div
              key={taskId}
              className="rounded-xl border bg-card p-4 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                <span className="text-sm text-muted-foreground">连接任务…</span>
              </div>
            </div>
          );
        }
        return (
          <DeployTaskCard
            key={taskId}
            state={state}
            logs={state.logs || []}
          />
        );
      })}
    </div>
  );
}
