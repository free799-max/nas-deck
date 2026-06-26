/**
 * 部署任务全局状态上下文
 *
 * 提供跨页面共享的“正在部署”任务列表与统一进度弹窗。
 * - startTask：添加任务并自动弹出进度弹窗
 * - removeTask：移除任务
 * - openPanel / closePanel / togglePanel：控制进度弹窗显隐
 */

import {
  createContext,
  useCallback,
  useEffect,
  useState,
} from "react";

interface DeployTaskContextValue {
  activeTaskIds: string[];
  isPanelOpen: boolean;
  startTask: (taskId: string) => void;
  removeTask: (taskId: string) => void;
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const DeployTaskContext = createContext<DeployTaskContextValue | null>(
  null
);

export function DeployTaskProvider({ children }: { children: React.ReactNode }) {
  const [activeTaskIds, setActiveTaskIds] = useState<string[]>([]);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  const startTask = useCallback((taskId: string) => {
    if (!taskId) return;
    setActiveTaskIds((prev) => {
      if (prev.includes(taskId)) return prev;
      return [...prev, taskId];
    });
    setIsPanelOpen(true);
  }, []);

  const removeTask = useCallback((taskId: string) => {
    setActiveTaskIds((prev) => prev.filter((id) => id !== taskId));
  }, []);

  const openPanel = useCallback(() => setIsPanelOpen(true), []);
  const closePanel = useCallback(() => setIsPanelOpen(false), []);
  const togglePanel = useCallback(
    () => setIsPanelOpen((prev) => !prev),
    []
  );

  // 所有任务结束（或清空）后自动关闭弹窗
  useEffect(() => {
    if (activeTaskIds.length === 0 && isPanelOpen) {
      setIsPanelOpen(false);
    }
  }, [activeTaskIds.length, isPanelOpen]);

  return (
    <DeployTaskContext.Provider
      value={{
        activeTaskIds,
        isPanelOpen,
        startTask,
        removeTask,
        openPanel,
        closePanel,
        togglePanel,
      }}
    >
      {children}
    </DeployTaskContext.Provider>
  );
}
