/**
 * 目录选择器弹窗
 *
 * 允许用户浏览宿主机文件系统并选择一个目录路径。
 */

import { useState, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDirectories } from "@/hooks/useHost";
import { Folder, ChevronRight, Home, Loader2 } from "lucide-react";

interface DirectoryPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialPath?: string;
  onSelect: (path: string) => void;
}

export function DirectoryPicker({
  open,
  onOpenChange,
  initialPath = "/",
  onSelect,
}: DirectoryPickerProps) {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [inputPath, setInputPath] = useState(initialPath);

  const { data, isLoading, error } = useDirectories(currentPath, open);

  const breadcrumbs = useMemo(() => {
    const parts = currentPath.split("/").filter(Boolean);
    const crumbs = [{ name: "根目录", path: "/" }];
    let acc = "";
    for (const part of parts) {
      acc += `/${part}`;
      crumbs.push({ name: part, path: acc });
    }
    return crumbs;
  }, [currentPath]);

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
    setInputPath(path);
  };

  const handleInputSubmit = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      const trimmed = inputPath.trim() || "/";
      setCurrentPath(trimmed);
    }
  };

  const handleSelect = () => {
    onSelect(currentPath);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[80vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader className="px-4 pt-4 pb-2 flex-shrink-0">
          <DialogTitle>选择目录</DialogTitle>
        </DialogHeader>

        <div className="px-4 pb-2 flex-shrink-0 space-y-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
            {breadcrumbs.map((crumb, index) => (
              <button
                key={crumb.path}
                type="button"
                onClick={() => handleNavigate(crumb.path)}
                className="hover:text-primary hover:underline flex items-center gap-0.5"
              >
                {index === 0 ? <Home className="h-3 w-3" /> : crumb.name}
                {index < breadcrumbs.length - 1 && (
                  <ChevronRight className="h-3 w-3" />
                )}
              </button>
            ))}
          </div>

          <Input
            value={inputPath}
            onChange={(e) => setInputPath(e.target.value)}
            onKeyDown={handleInputSubmit}
            placeholder="输入绝对路径后回车跳转"
            className="h-8 text-sm"
          />
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-1">
          {isLoading && (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              加载中…
            </div>
          )}

          {error && !isLoading && (
            <div className="py-6 text-center text-sm text-destructive">
              无法读取该路径：{(error as Error)?.message || "未知错误"}
            </div>
          )}

          {!isLoading && !error && data && (
            <div className="space-y-0.5">
              {currentPath !== "/" && (
                <button
                  type="button"
                  onClick={() => {
                    const parent = currentPath.replace(/\/[^/]*\/?$/, "") || "/";
                    handleNavigate(parent);
                  }}
                  className="w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left hover:bg-muted"
                >
                  <Folder className="h-4 w-4 text-muted-foreground" />
                  ..
                </button>
              )}

              {data.entries.length === 0 && (
                <div className="py-6 text-center text-xs text-muted-foreground">
                  该目录下没有子目录
                </div>
              )}

              {data.entries.map((entry) => (
                <button
                  key={entry.path}
                  type="button"
                  onClick={() => handleNavigate(entry.path)}
                  className="w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left hover:bg-muted"
                >
                  <Folder className="h-4 w-4 text-primary" />
                  {entry.name}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 px-4 py-3 border-t flex-shrink-0">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button size="sm" onClick={handleSelect}>
            选择当前目录
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
