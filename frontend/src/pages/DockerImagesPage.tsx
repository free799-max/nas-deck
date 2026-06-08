/**
 * Docker 镜像管理页面（重构版）
 *
 * 上下双区域布局：
 * - 上区域：镜像搜索配置 + 远程镜像搜索/拉取
 * - 下区域：本地镜像管理，支持多选批量删除
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
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
  useSearchImages,
  usePullImage,
  useBatchRemoveImages,
  useRegistries,
  useCreateRegistry,
  useUpdateRegistry,
  useDeleteRegistry,
  useSetDefaultRegistry,
  type Registry,
  type RegistryCreate,
} from "@/hooks/useDocker";
import { useToast } from "@/components/ui/toast";
import {
  Trash2,
  Search,
  Download,
  Star,
  Shield,
  HardDrive,
  Loader2,
  Settings,
  AlertTriangle,
  Plus,
  Edit2,
  CheckCircle,
  X,
  User,
  Lock,
} from "lucide-react";

/** 字节转人类可读 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

/** ISO 日期转本地短格式 */
function formatDate(iso: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString("zh-CN");
}

/* ------------------------------------------------------------------ */
export function DockerImagesPage() {
  const toast = useToast();

  /* ---------- 上区域：Registry 配置 ---------- */
  const { data: registries = [] } = useRegistries();
  const createRegistry = useCreateRegistry();
  const updateRegistry = useUpdateRegistry();
  const deleteRegistry = useDeleteRegistry();
  const setDefaultRegistry = useSetDefaultRegistry();

  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingRegistry, setEditingRegistry] = useState<Registry | null>(
    null
  );
  const [editForm, setEditForm] = useState<RegistryCreate>({
    name: "",
    search_api_url: "",
    mirror_url: null,
    enable_mirror: false,
    username: null,
    password: null,
  });

  const openCreateDialog = () => {
    setEditingRegistry(null);
    setEditForm({
      name: "",
      search_api_url: "",
      mirror_url: null,
      enable_mirror: false,
      username: null,
      password: null,
    });
    setShowEditDialog(true);
  };

  const openEditDialog = (registry: Registry) => {
    setEditingRegistry(registry);
    setEditForm({
      name: registry.name,
      search_api_url: registry.search_api_url,
      mirror_url: registry.mirror_url,
      enable_mirror: registry.enable_mirror,
      username: registry.username,
      password: null,
    });
    setShowEditDialog(true);
  };

  const handleSaveRegistry = () => {
    if (!editForm.name.trim() || !editForm.search_api_url.trim()) {
      toast.error("名称和主地址不能为空");
      return;
    }
    const payload: RegistryCreate = {
      name: editForm.name.trim(),
      search_api_url: editForm.search_api_url.trim(),
      mirror_url: editForm.mirror_url?.trim() || null,
      enable_mirror: editForm.enable_mirror,
      username: editForm.username?.trim() || null,
      password: editForm.password?.trim() || null,
    };
    // 编辑时若密码为空，不传递 password 字段以避免覆盖原有密码
    if (editingRegistry && !editForm.password?.trim()) {
      delete (payload as any).password;
    }
    if (editingRegistry) {
      updateRegistry.mutate(
        { id: editingRegistry.id, data: payload },
        { onSuccess: () => setShowEditDialog(false) }
      );
    } else {
      createRegistry.mutate(payload, {
        onSuccess: () => setShowEditDialog(false),
      });
    }
  };

  const handleDeleteRegistry = (id: number) => {
    if (confirm("确定删除此配置吗？")) {
      deleteRegistry.mutate(id);
    }
  };

  const handleSetDefault = (id: number) => {
    setDefaultRegistry.mutate(id);
  };

  /* ---------- 上区域：搜索 ---------- */
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [pullingName, setPullingName] = useState<string | null>(null);

  const { data: searchResults = [], isLoading: searchLoading } =
    useSearchImages(searchQuery);
  const pullImage = usePullImage();

  const handleSearch = () => {
    if (!searchInput.trim()) {
      toast.error("请输入搜索关键词");
      return;
    }
    setSearchQuery(searchInput.trim());
  };

  const handlePull = (name: string) => {
    setPullingName(name);
    pullImage.mutate(name, {
      onSettled: () => setPullingName(null),
    });
  };

  /* ---------- 下区域：本地镜像 ---------- */
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

  const defaultRegistry = registries.find((r) => r.is_default);

  return (
    <div className="space-y-6">
      {/* ==================== 上区域：配置 + 搜索 ==================== */}
      <Card className="rounded-xl">
        <CardContent className="p-4 space-y-4">
          {/* 头部：标题 + 当前配置 + 配置按钮 */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <Settings className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-medium">镜像搜索</h2>
            </div>
            <div className="flex items-center gap-3">
              {defaultRegistry && (
                <Badge
                  variant="outline"
                  className="text-xs bg-primary/5 text-primary border-primary/20 font-normal"
                >
                  <CheckCircle className="h-3 w-3 mr-1" />
                  {defaultRegistry.name}
                </Badge>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowConfigDialog(true)}
              >
                <Settings className="h-4 w-4 mr-1" />
                管理配置
              </Button>
            </div>
          </div>

          <Separator />

          {/* 搜索框 */}
          <div className="flex gap-2">
            <Input
              placeholder="搜索镜像（如 nginx、redis）"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1 h-9"
            />
            <Button size="sm" onClick={handleSearch} disabled={searchLoading}>
              {searchLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              <span className="ml-2">搜索</span>
            </Button>
          </div>

          {/* 搜索结果 */}
          {searchQuery && searchResults.length === 0 && !searchLoading ? (
            <p className="text-muted-foreground text-sm text-center py-6">
              未找到与 &quot;{searchQuery}&quot; 相关的镜像。
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-2">
              {searchResults.map((r) => (
                <Card
                  key={r.name}
                  className="rounded-lg transition-shadow hover:shadow-elevated"
                >
                  <CardContent className="p-3 flex items-center justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold text-sm truncate">
                          {r.name}
                        </span>
                        {r.official && (
                          <Badge
                            variant="default"
                            className="text-xs bg-primary/10 text-primary border-primary/20"
                          >
                            <Shield className="h-3 w-3 mr-1" />
                            Official
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {r.description || "暂无描述"}
                      </p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Star className="h-3 w-3" />
                          {r.star_count}
                        </span>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handlePull(r.name)}
                      disabled={pullingName === r.name}
                    >
                      {pullingName === r.name ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                      <span className="ml-1">拉取</span>
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ==================== Registry 配置 Dialog ==================== */}
      <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>镜像仓库设置</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* 工具栏 */}
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={openCreateDialog}>
                <Plus className="h-4 w-4 mr-1" />
                新增
              </Button>
            </div>

            <div className="border rounded-xl overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">状态</TableHead>
                    <TableHead>名称</TableHead>
                    <TableHead>搜索地址</TableHead>
                    <TableHead>镜像地址</TableHead>
                    <TableHead className="text-right w-48">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {registries.map((registry) => (
                    <TableRow key={registry.id}>
                      <TableCell>
                        {registry.is_default ? (
                          <Badge className="text-xs bg-primary/10 text-primary border-primary/20">
                            使用中
                          </Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            -
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="font-medium text-sm">
                        {registry.name}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        <span className="font-mono">{registry.search_api_url}</span>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {registry.mirror_url || "-"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs"
                            onClick={() => handleSetDefault(registry.id)}
                            disabled={
                              registry.is_default ||
                              setDefaultRegistry.isPending
                          }
                          >
                            <CheckCircle className="h-3.5 w-3.5 mr-1" />
                            使用
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 w-8 p-0"
                            onClick={() => openEditDialog(registry)}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          {!registry.is_default && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 w-8 p-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                              onClick={() =>
                                handleDeleteRegistry(registry.id)
                              }
                              disabled={deleteRegistry.isPending}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {registries.length === 0 && (
                    <TableRow>
                      <TableCell
                        colSpan={5}
                        className="text-center text-muted-foreground py-6"
                      >
                        暂无配置，请添加镜像仓库。
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ==================== 新增/编辑 Registry Dialog ==================== */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingRegistry ? "编辑配置" : "新增配置"}
            </DialogTitle>
            <DialogDescription>
              {editingRegistry
                ? "修改镜像搜索接口的配置信息"
                : "添加新的 Docker 镜像搜索接口配置"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-5 py-2">
            {/* 基础配置 */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                基础配置
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="reg-name" className="text-sm">
                    配置名称 <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="reg-name"
                    placeholder="如 Docker Hub 官方"
                    value={editForm.name}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        name: e.target.value,
                      }))
                    }
                    className="h-9"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reg-url" className="text-sm">
                    搜索 API 主地址{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="reg-url"
                    placeholder="如 https://hub.docker.com/v2/search/repositories"
                    value={editForm.search_api_url}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        search_api_url: e.target.value,
                      }))
                    }
                    className="h-9"
                  />
                </div>
              </div>
            </div>

            <Separator />

            {/* 镜像容错配置 */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                镜像容错配置
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="reg-mirror" className="text-sm">
                    镜像搜索 API 地址
                  </Label>
                  <Input
                    id="reg-mirror"
                    placeholder="如 https://mirror.example.com/v2/search/repositories"
                    value={editForm.mirror_url || ""}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        mirror_url: e.target.value || null,
                      }))
                    }
                    className="h-9"
                  />
                </div>
                <div className="flex items-end pb-1">
                  <label className="flex items-center gap-2.5 cursor-pointer group">
                    <div className="relative">
                      <input
                        id="reg-enable-mirror"
                        type="checkbox"
                        checked={editForm.enable_mirror}
                        onChange={(e) =>
                          setEditForm((prev) => ({
                            ...prev,
                            enable_mirror: e.target.checked,
                          }))
                        }
                        className="peer sr-only"
                      />
                      <div className="h-5 w-9 rounded-full bg-muted-foreground/30 transition-colors peer-checked:bg-primary" />
                      <div className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-4" />
                    </div>
                    <span className="text-sm text-foreground group-hover:text-foreground/80 transition-colors">
                      启用镜像地址作为容错 fallback
                    </span>
                  </label>
                </div>
              </div>
            </div>

            <Separator />

            {/* 认证配置 */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                认证配置（可选）
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="reg-username" className="text-sm">
                    <span className="flex items-center gap-1">
                      <User className="h-3.5 w-3.5" />
                      用户名
                    </span>
                  </Label>
                  <Input
                    id="reg-username"
                    placeholder="认证用户名"
                    value={editForm.username || ""}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        username: e.target.value || null,
                      }))
                    }
                    className="h-9"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reg-password" className="text-sm">
                    <span className="flex items-center gap-1">
                      <Lock className="h-3.5 w-3.5" />
                      密码
                    </span>
                  </Label>
                  <Input
                    id="reg-password"
                    type="password"
                    placeholder={
                      editingRegistry ? "留空则不修改" : "认证密码"
                    }
                    value={editForm.password || ""}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        password: e.target.value || null,
                      }))
                    }
                    className="h-9"
                  />
                </div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              <X className="h-4 w-4 mr-1" />
              取消
            </Button>
            <Button
              onClick={handleSaveRegistry}
              disabled={createRegistry.isPending || updateRegistry.isPending}
            >
              {createRegistry.isPending || updateRegistry.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : null}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ==================== 下区域：本地镜像 ==================== */}
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
    </div>
  );
}
