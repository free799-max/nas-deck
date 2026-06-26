/**
 * 部署任务进度弹窗
 *
 * 全局统一的浮层，展示所有进行中的部署任务进度。
 * 关闭后可通过顶部栏的动态入口重新打开。
 */

import { useCallback, useEffect, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DeployProgressPanel } from "@/components/DeployProgressPanel";
import { useDeployTasks } from "@/hooks/useDeployTasks";
import { useToast } from "@/components/ui/toast";

const DISMISS_DELAY_MS = 3000;

export function DeployProgressDialog() {
  const { activeTaskIds, isPanelOpen, closePanel, removeTask } = useDeployTasks();
  const toast = useToast();
  const timersRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());

  useEffect(() => {
    return () => {
      timersRef.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  const handleComplete = useCallback(
    (taskId: string) => {
      toast.success("部署完成");
      const t = setTimeout(() => removeTask(taskId), DISMISS_DELAY_MS);
      timersRef.current.add(t);
    },
    [removeTask, toast]
  );

  const handleError = useCallback(
    (taskId: string, state: { error?: string | null }) => {
      toast.error(state.error || "部署失败");
      const t = setTimeout(() => removeTask(taskId), DISMISS_DELAY_MS);
      timersRef.current.add(t);
    },
    [removeTask, toast]
  );

  if (activeTaskIds.length === 0) {
    return null;
  }

  return (
    <Dialog open={isPanelOpen} onOpenChange={(open) => !open && closePanel()}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col p-0 overflow-hidden">
        <DialogHeader className="px-5 pt-5 pb-3 border-b shrink-0">
          <DialogTitle>部署进度</DialogTitle>
        </DialogHeader>
        <div className="px-5 py-4 overflow-y-auto">
          <DeployProgressPanel
            taskIds={activeTaskIds}
            onComplete={handleComplete}
            onError={handleError}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
