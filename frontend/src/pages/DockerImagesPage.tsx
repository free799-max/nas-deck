/**
 * Docker 镜像管理页面
 *
 * 提供本地镜像管理和远程镜像搜索拉取功能：
 * - 本地镜像：列表展示、删除
 * - 远程搜索：Docker Hub 搜索、拉取镜像
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  useImages,
  useRemoveImage,
  useSearchImages,
  usePullImage,
} from "@/hooks/useDocker";
import { useToast } from "@/components/ui/toast";
import {
  Trash2,
  Search,
  Download,
  Star,
  Shield,
  HardDrive,
  Globe,
  Loader2,
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
  const [activeTab, setActiveTab] = useState<"local" | "remote">("local");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pullingName, setPullingName] = useState<string | null>(null);
  const toast = useToast();

  const { data: images = [], isLoading: imagesLoading } = useImages();
  const removeImage = useRemoveImage();
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

  const handleDelete = (id: string) => {
    setDeletingId(id);
    removeImage.mutate(
      { id },
      {
        onSettled: () => setDeletingId(null),
      }
    );
  };

  const handlePull = (name: string) => {
    setPullingName(name);
    pullImage.mutate(name, {
      onSettled: () => setPullingName(null),
    });
  };

  return (
    <div>

      <Card className="rounded-xl">
        <CardContent className="p-3 space-y-3">
          {/* Tab 切换 */}
          <div className="flex gap-1 bg-muted p-1 rounded-xl w-fit">
            <button
              onClick={() => setActiveTab("local")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === "local"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <span className="flex items-center gap-2">
                <HardDrive className="h-4 w-4" />
                本地镜像
              </span>
            </button>
            <button
              onClick={() => setActiveTab("remote")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === "remote"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <span className="flex items-center gap-2">
                <Globe className="h-4 w-4" />
                远程搜索
              </span>
            </button>
          </div>

          {/* ========== 本地镜像 ========== */}
          {activeTab === "local" && (
            <>
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
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>
                        <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                          镜像 ID
                        </th>
                        <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                          标签
                        </th>
                        <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                          大小
                        </th>
                        <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                          创建时间
                        </th>
                        <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                          容器
                        </th>
                        <th className="text-right px-4 py-3 font-medium text-muted-foreground">
                          操作
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {images.map((img) => (
                        <tr key={img.id} className="hover:bg-muted/50">
                          <td className="px-4 py-3 font-mono text-xs">
                            {img.id}
                          </td>
                          <td className="px-4 py-3">
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
                          </td>
                          <td className="px-4 py-3">{formatBytes(img.size)}</td>
                          <td className="px-4 py-3 text-muted-foreground">
                            {formatDate(img.created)}
                          </td>
                          <td className="px-4 py-3">
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
                          </td>
                          <td className="px-4 py-3 text-right">
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
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {/* ========== 远程搜索 ========== */}
          {activeTab === "remote" && (
            <div className="space-y-4">
              {/* 搜索框 */}
              <div className="flex gap-2">
                <Input
                  placeholder="搜索 Docker Hub 镜像（如 nginx、redis）"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  className="flex-1"
                />
                <Button onClick={handleSearch} disabled={searchLoading}>
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
                <p className="text-muted-foreground text-center py-12">
                  未找到与 "{searchQuery}" 相关的镜像。
                </p>
              ) : (
                <div className="grid grid-cols-1 gap-3">
                  {searchResults.map((r) => (
                    <Card key={r.name} className="rounded-xl">
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
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
