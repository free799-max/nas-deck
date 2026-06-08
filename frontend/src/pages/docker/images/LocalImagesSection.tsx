/**
 * 本地镜像管理区域组件
 *
 * 表格展示本地镜像列表，支持多选和批量删除。
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useImages,
  useRemoveImage,
  useBatchRemoveImages,
} from "@/hooks/useDocker";
import { formatBytes, formatDate } from "@/lib/utils";
import {
  Trash2,
  HardDrive,
  Loader2,
  AlertTriangle,
} from "lucide-react";

export function LocalImagesSection() {
  const { data: images = [], isLoading: imagesLoading } = useImages();
  const removeImage = useRemoveImage();
  const batchRemoveImages = useBatchRemoveImages();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showBatchDeleteDialog, setShowBatchDeleteDialog] = useState(false);

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedIds(next);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === images.length && images.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(images.map((img) => img.id)));
    }
  };

  const handleDelete = (id: string) => {
    setDeletingId(id);
    removeImage.mutate(
      { id },
      {
        onSettled: () => {
          setDeletingId(null);
          setSelectedIds((prev) => {
            const next = new Set(prev);
            next.delete(id);
            return next;
          });
        },
      }
    );
  };

  const handleBatchDelete = () => {
    if (selectedIds.size === 0) return;
    setShowBatchDeleteDialog(true);
  };

  const confirmBatchDelete = () => {
    batchRemoveImages.mutate(
      { ids: Array.from(selectedIds), force: false },
      {
        onSettled: () => {
          setShowBatchDeleteDialog(false);
          setSelectedIds(new Set());
        },
      }
    );
  };

  const allSelected = images.length > 0 && selectedIds.size === images.length;

  return (
    <>
      <Card className="rounded-xl">
        <CardContent className="p-4 space-y-4">
          {/* 头部 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-medium">本地镜像</h2>
              {selectedIds.size > 0 && (
                <Badge variant="outline" className="text-xs">
                  已选 {selectedIds.size} 个
                </Badge>
              )}
            </div>
            {selectedIds.size > 0 && (
              <Button
                size="sm"
                variant="destructive"
                onClick={handleBatchDelete}
                disabled={batchRemoveImages.isPending}
              >
                {batchRemoveImages.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
                <span className="ml-2">批量删除</span>
              </Button>
            )}
          </div>

          {/* 镜像表格 */}
          {imagesLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : images.length === 0 ? (
            <p className="text-muted-foreground text-center py-12">
              暂无本地镜像。
            </p>
          ) : (
            <div className="border rounded-xl overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10 px-4">
                      <input
                        type="checkbox"
                        role="checkbox"
                        checked={allSelected}
                        onChange={toggleSelectAll}
                        className="h-4 w-4 rounded border-input cursor-pointer"
                      />
                    </TableHead>
                    <TableHead>镜像 ID</TableHead>
                    <TableHead>标签</TableHead>
                    <TableHead>大小</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>容器</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {images.map((img) => (
                    <TableRow
                      key={img.id}
                      data-state={
                        selectedIds.has(img.id) ? "selected" : undefined
                      }
                    >
                      <TableCell className="px-4">
                        <input
                          type="checkbox"
                          role="checkbox"
                          checked={selectedIds.has(img.id)}
                          onChange={() => toggleSelect(img.id)}
                          className="h-4 w-4 rounded border-input cursor-pointer"
                        />
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {img.id}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {img.tags.map((tag) => (
                            <Badge
                              key={tag}
                              variant="outline"
                              className="text-xs"
                            >
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>{formatBytes(img.size)}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(img.created)}
                      </TableCell>
                      <TableCell>
                        {img.containers > 0 ? (
                          <Badge
                            variant="default"
                            className="text-xs bg-primary/10 text-primary border-primary/20"
                          >
                            {img.containers} 个
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 w-8 p-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                          onClick={() => handleDelete(img.id)}
                          disabled={deletingId === img.id}
                        >
                          {deletingId === img.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 批量删除确认对话框 */}
      <Dialog
        open={showBatchDeleteDialog}
        onOpenChange={setShowBatchDeleteDialog}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              确认批量删除
            </DialogTitle>
            <DialogDescription>
              确定要删除选中的 <strong>{selectedIds.size}</strong>{" "}
              个镜像吗？此操作不可恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter showCloseButton>
            <Button
              variant="destructive"
              onClick={confirmBatchDelete}
              disabled={batchRemoveImages.isPending}
            >
              {batchRemoveImages.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              <span className="ml-2">确认删除</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
