/**
 * 编排实例组管理器
 *
 * 以胶囊 Tab 形式展示多个实例组，支持切换、重命名和删除。
 * 设计为放置在页面头部，与操作按钮平行排列。
 */

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Pencil, Trash2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { OrchestrationInstanceGroup } from "@/hooks/useOrchestrations";

interface OrchestrationInstanceManagerProps {
  instances: OrchestrationInstanceGroup[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRename: (id: number, name: string) => void;
  onDelete: (id: number) => void;
  isPending?: boolean;
}

export function OrchestrationInstanceManager({
  instances,
  selectedId,
  onSelect,
  onRename,
  onDelete,
  isPending = false,
}: OrchestrationInstanceManagerProps) {
  const [renameInstance, setRenameInstance] =
    useState<OrchestrationInstanceGroup | null>(null);
  const [deleteInstance, setDeleteInstance] =
    useState<OrchestrationInstanceGroup | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const selectedInstance =
    instances.find((i) => i.id === selectedId) ?? instances[0];

  const handleOpenRename = (instance: OrchestrationInstanceGroup) => {
    setRenameInstance(instance);
    setRenameValue(instance.instance_name);
  };

  const handleConfirmRename = () => {
    if (!renameInstance || !renameValue.trim()) return;
    onRename(renameInstance.id, renameValue.trim());
    setRenameInstance(null);
  };

  const handleConfirmDelete = () => {
    if (!deleteInstance) return;
    onDelete(deleteInstance.id);
    setDeleteInstance(null);
  };

  if (instances.length === 0) {
    return null;
  }

  // 单个实例时不显示切换 Tab，仅保留操作入口
  if (instances.length === 1) {
    return (
      <>
        <button
          type="button"
          disabled={isPending}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground shadow-sm"
        >
          <span className="max-w-[100px] truncate block">
            {selectedInstance.instance_name}
          </span>
        </button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="icon-sm"
              className="h-9 w-9 rounded-lg bg-background border-border hover:bg-background/80"
              disabled={isPending}
            >
              <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" alignOffset={-16} className="w-28 min-w-0 rounded-md p-1">
            <DropdownMenuItem
              onClick={() => handleOpenRename(selectedInstance)}
              className="gap-2 px-2 py-1.5 text-xs"
            >
              <Pencil className="h-3.5 w-3.5" />
              重命名
            </DropdownMenuItem>
            <DropdownMenuItem
              variant="destructive"
              onClick={() => setDeleteInstance(selectedInstance)}
              className="gap-2 px-2 py-1.5 text-xs"
            >
              <Trash2 className="h-3.5 w-3.5" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {renderDialogs()}
      </>
    );
  }

  return (
    <>
      <div className="flex items-center gap-0.5 rounded-lg bg-muted p-1">
        {instances.map((instance) => {
          const active = selectedId === instance.id;
          return (
            <button
              key={instance.id}
              type="button"
              disabled={isPending}
              onClick={() => onSelect(instance.id)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="max-w-[100px] truncate block">
                {instance.instance_name}
              </span>
            </button>
          );
        })}
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            className="h-8 w-8"
            disabled={isPending}
          >
            <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" alignOffset={-16} className="w-28 min-w-0 rounded-md p-1">
          <DropdownMenuItem
            onClick={() => {
              if (selectedInstance) handleOpenRename(selectedInstance);
            }}
            className="gap-2 px-2 py-1.5 text-xs"
          >
            <Pencil className="h-3.5 w-3.5" />
            重命名
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onClick={() => {
              if (selectedInstance) setDeleteInstance(selectedInstance);
            }}
            className="gap-2 px-2 py-1.5 text-xs"
          >
            <Trash2 className="h-3.5 w-3.5" />
            删除
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {renderDialogs()}
    </>
  );

  function renderDialogs() {
    return (
      <>
        <Dialog
          open={!!renameInstance}
          onOpenChange={() => setRenameInstance(null)}
        >
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>重命名实例组</DialogTitle>
            </DialogHeader>
            <div className="py-2">
              <Input
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                placeholder="实例组名称"
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setRenameInstance(null)}
                disabled={isPending}
              >
                取消
              </Button>
              <Button
                onClick={handleConfirmRename}
                disabled={!renameValue.trim() || isPending}
              >
                保存
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog
          open={!!deleteInstance}
          onOpenChange={() => setDeleteInstance(null)}
        >
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-destructive" />
                删除实例组
              </DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground py-2">
              确认删除实例组「{deleteInstance?.instance_name}」？
              关联的应用实例和 Docker 项目将被一并清理，此操作不可撤销。
            </p>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setDeleteInstance(null)}
                disabled={isPending}
              >
                取消
              </Button>
              <Button
                variant="destructive"
                onClick={handleConfirmDelete}
                disabled={isPending}
              >
                删除
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    );
  }
}
