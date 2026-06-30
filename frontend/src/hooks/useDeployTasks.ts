/**
 * 部署任务相关 React hooks
 *
 * 提供应用商店和 Compose 部署任务的 SSE 进度监听。
 */

import { useEffect, useRef, useState } from "react";

import { useContext } from "react";
import { DeployTaskContext } from "@/contexts/DeployTaskContext";

/** 获取全局部署任务上下文 */
export function useDeployTasks() {
  const ctx = useContext(DeployTaskContext);
  if (!ctx) {
    throw new Error("useDeployTasks 必须在 DeployTaskProvider 内使用");
  }
  return ctx;
}

/** 部署任务进度 */
export interface DeployTaskProgress {
  stage: string;
  percentage: number;
  message: string;
  detail?: string | null;
}

/** SSE 事件数据 */
interface DeployTaskEvent extends DeployTaskProgress {
  _task_status?: "deploying" | "completed" | "failed";
  _error?: string;
  _meta?: Record<string, unknown> | null;
}

/** 部署任务状态 */
export interface DeployTaskState {
  taskId: string;
  type: string;
  status: "deploying" | "completed" | "failed";
  stage: string;
  progress: DeployTaskProgress;
  error?: string | null;
  action?: string | null;
  projectId?: number | null;
  instanceId?: number | null;
  meta?: Record<string, unknown> | null;
  logs?: string[];
}

function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || "";
}

function parseDeployEvent(taskId: string, eventData: string): DeployTaskState | null {
  try {
    const data = JSON.parse(eventData) as DeployTaskEvent;
    const taskStatus = data._task_status || "deploying";
    return {
      taskId,
      type: data.stage?.startsWith("compose") ? "compose" : "app_deploy",
      status: taskStatus,
      stage: data.stage,
      progress: {
        stage: data.stage,
        percentage: data.percentage,
        message: data.message,
        detail: data.detail,
      },
      error: data._error || null,
      meta: data._meta,
    };
  } catch {
    return null;
  }
}

const statusWordMap: Record<string, string> = {
  Creating: "创建中",
  Created: "已创建",
  Starting: "启动中",
  Started: "已启动",
  Stopping: "停止中",
  Stopped: "已停止",
  Removing: "删除中",
  Removed: "已删除",
  Waiting: "等待中",
  Pulling: "拉取中",
  Pulled: "已拉取",
  Extracting: "解压中",
  Downloading: "下载中",
  Downloaded: "已下载",
  Building: "构建中",
  Built: "已构建",
  Running: "运行中",
  Error: "错误",
  Done: "完成",
};

function translateStatusWord(line: string): string {
  const tokens = line.trim().split(/\s+/);
  if (tokens.length === 0) return line;
  const last = tokens[tokens.length - 1];
  if (statusWordMap[last]) {
    tokens[tokens.length - 1] = statusWordMap[last];
  }
  return tokens.join(" ");
}

const ANSI_ESC = String.fromCharCode(27);

function stripAnsi(text: string): string {
  // 移除 ANSI 转义序列（颜色、光标移动、清行等）
  return text.replace(
    new RegExp(`${ANSI_ESC}(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])`, "g"),
    ""
  );
}

function cleanDetailLine(detail: string): string {
  // 把 docker compose 输出里的 Network/Container 翻译成中文，并去掉前置空格、翻译状态词
  const translatedPrefix = stripAnsi(detail)
    .trimStart()
    .replace(/^Network\s+/, "网络 ")
    .replace(/^Container\s+/, "容器 ");
  return translateStatusWord(translatedPrefix);
}

/**
 * 判断一行日志是否属于单个包的下载/安装进度条。
 * 例如："click ------------------------------ 94.81 KiB/116.45 KiB"
 */
function isProgressLine(line: string): boolean {
  return /\d+(\.\d+)?\s*(KiB|MiB|GiB)\s*\/\s*\d+(\.\d+)?\s*(KiB|MiB|GiB)/.test(line);
}

/**
 * 提取进度条行的包名/标识前缀，用于判断是否可以覆盖上一条同类进度。
 */
function progressLineKey(line: string): string | null {
  const match = line.match(/^(\S+)/);
  return match ? match[1] : null;
}

function appendDeployLogs(
  existing: DeployTaskState | undefined,
  next: DeployTaskState
): string[] {
  const logs = existing?.logs ? [...existing.logs] : [];
  const lastMessage = existing?.progress.message;
  const lastDetail = existing?.progress.detail;
  const message = next.progress.message;
  const detail = next.progress.detail;

  if (message && message !== lastMessage) {
    logs.push(message);
  }
  if (detail) {
    const cleaned = cleanDetailLine(detail);
    const lastCleaned = lastDetail ? cleanDetailLine(lastDetail) : undefined;
    if (cleaned && cleaned !== lastCleaned) {
      // 对单个包的进度条进行覆盖：相同包名的进度只保留最新一帧，避免刷屏
      if (isProgressLine(cleaned)) {
        const key = progressLineKey(cleaned);
        if (key && logs.length > 0) {
          const lastLog = logs[logs.length - 1];
          if (isProgressLine(lastLog) && progressLineKey(lastLog) === key) {
            logs[logs.length - 1] = cleaned;
            return logs;
          }
        }
      }
      logs.push(cleaned);
    }
  }
  return logs;
}

/**
 * 监听单个部署任务的 SSE 实时进度
 */
export function useDeployTaskEvents(
  taskId: string | null,
  onComplete?: (state: DeployTaskState) => void,
  onError?: (state: DeployTaskState) => void
): DeployTaskState | null {
  const [state, setState] = useState<DeployTaskState | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!taskId) {
      setState(null);
      return;
    }

    const baseUrl = getApiBaseUrl();
    const token = localStorage.getItem("token") || "";
    const url = `${baseUrl}/api/deploy-tasks/${taskId}/events?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      const newState = parseDeployEvent(taskId, event.data);
      if (!newState) return;

      setState((prev) => {
        const logs = appendDeployLogs(prev ?? undefined, newState);
        return { ...newState, logs };
      });

      if (newState.status === "completed") {
        onComplete?.(newState);
        es.close();
      } else if (newState.status === "failed") {
        onError?.(newState);
        es.close();
      }
    };

    es.onerror = () => {
      // SSE 连接错误时关闭，调用方可选择重连或提示
      es.close();
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [taskId, onComplete, onError]);

  return state;
}

/**
 * 同时监听多个部署任务的 SSE 实时进度
 */
export function useDeployTasksEvents(
  taskIds: string[],
  onComplete?: (taskId: string, state: DeployTaskState) => void,
  onError?: (taskId: string, state: DeployTaskState) => void
): Record<string, DeployTaskState> {
  const [states, setStates] = useState<Record<string, DeployTaskState>>({});
  const taskIdsKey = taskIds.join(",");

  useEffect(() => {
    if (taskIds.length === 0) {
      setStates({});
      return;
    }

    const baseUrl = getApiBaseUrl();
    const token = localStorage.getItem("token") || "";
    const sources: Record<string, EventSource> = {};

    taskIds.forEach((taskId) => {
      const url = `${baseUrl}/api/deploy-tasks/${taskId}/events?token=${encodeURIComponent(token)}`;
      const es = new EventSource(url);
      sources[taskId] = es;

      es.onmessage = (event) => {
        const newState = parseDeployEvent(taskId, event.data);
        if (!newState) return;

        setStates((prev) => {
          const existing = prev[taskId];
          const logs = appendDeployLogs(existing, newState);
          return { ...prev, [taskId]: { ...newState, logs } };
        });

        if (newState.status === "completed") {
          onComplete?.(taskId, newState);
          es.close();
        } else if (newState.status === "failed") {
          onError?.(taskId, newState);
          es.close();
        }
      };

      es.onerror = () => {
        es.close();
      };
    });

    return () => {
      Object.values(sources).forEach((es) => es.close());
    };
  }, [taskIdsKey, taskIds, onComplete, onError]);

  return states;
}
