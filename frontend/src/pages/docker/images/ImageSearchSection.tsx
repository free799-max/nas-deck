/**
 * 镜像搜索区域组件
 *
 * 包含搜索输入框和远程镜像搜索结果列表，支持拉取操作。
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  useSearchImages,
  usePullImage,
  type Registry,
} from "@/hooks/useDocker";
import { useToast } from "@/components/ui/toast";
import {
  Search,
  Download,
  Star,
  Shield,
  Loader2,
  Settings,
  CheckCircle,
} from "lucide-react";

interface ImageSearchSectionProps {
  defaultRegistry: Registry | undefined;
  onOpenConfig: () => void;
}

export function ImageSearchSection({ defaultRegistry, onOpenConfig }: ImageSearchSectionProps) {
  const toast = useToast();

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

  return (
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
              onClick={onOpenConfig}
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
  );
}
