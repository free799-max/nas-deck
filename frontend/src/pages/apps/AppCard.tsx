/**
 * 应用卡片组件
 *
 * 应用商店风格：左侧图标、右侧信息 + 底部操作栏。
 */

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pencil } from "lucide-react";
import { AppIcon } from "./AppIcon";
import type { App } from "@/hooks/useApps";

interface AppCardProps {
  app: App;
  onDeploy: (app: App) => void;
  onDetail: (app: App) => void;
  /** 编辑入口（仅管理员显示） */
  onEdit?: (app: App) => void;
}

export function AppCard({ app, onDeploy, onDetail, onEdit }: AppCardProps) {
  return (
    <Card
      className="rounded-xl p-5 min-h-[140px] border border-border/80 shadow-sm hover:shadow-[0_4px_14px_rgba(0,0,0,0.08)] hover:border-border transition-all cursor-pointer"
      onClick={() => onDetail(app)}
    >
      <CardContent className="p-0 h-full flex items-stretch gap-5">
        {/* 图标 */}
        <div className="shrink-0 self-center">
          <AppIcon
            app={app}
            className="h-16 w-16 rounded-xl object-contain bg-white border border-border/60 text-2xl"
          />
        </div>

        {/* 信息区 */}
        <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
          <div>
            <h3 className="text-base font-semibold text-foreground truncate">
              {app.display_name}
            </h3>
            <p className="text-sm text-muted-foreground line-clamp-1 mt-1">
              {app.description || "暂无描述"}
            </p>
          </div>

          <div className="flex items-center justify-between mt-3">
            <div className="flex flex-wrap items-center gap-1.5 min-w-0">
              {app.tags.slice(0, 2).map((tag) => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="text-xs font-normal bg-muted text-muted-foreground hover:bg-muted truncate max-w-[80px]"
                >
                  {tag}
                </Badge>
              ))}
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              {onEdit && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(app);
                  }}
                  className="rounded-full h-7 w-7 p-0 text-muted-foreground hover:text-primary hover:bg-primary/5"
                  title="编辑应用"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeploy(app);
                }}
                className="rounded-full px-4 h-7 text-xs border-primary/30 text-primary hover:bg-primary/5 hover:text-primary hover:border-primary/40"
              >
                安装
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
