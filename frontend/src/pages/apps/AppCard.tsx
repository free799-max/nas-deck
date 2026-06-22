/**
 * 应用卡片组件
 *
 * 应用商店风格：左侧图标、右侧信息 + 底部操作栏。
 */

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { App } from "@/hooks/useApps";

interface AppCardProps {
  app: App;
  onDeploy: (app: App) => void;
  onDetail: (app: App) => void;
}

export function AppCard({ app, onDeploy, onDetail }: AppCardProps) {
  return (
    <Card
      className="rounded-xl p-5 min-h-[140px] border border-border/80 shadow-sm hover:shadow-[0_4px_14px_rgba(0,0,0,0.08)] hover:border-border transition-all cursor-pointer"
      onClick={() => onDetail(app)}
    >
      <CardContent className="p-0 h-full flex items-stretch gap-5">
        {/* 图标 */}
        <div className="shrink-0 self-center">
          {app.icon ? (
            <img
              src={
                app.icon.startsWith("http")
                  ? app.icon
                  : `/api/apps/${app.name}/icon`
              }
              alt={app.display_name}
              className="h-16 w-16 rounded-xl object-contain bg-white border border-border/60"
            />
          ) : (
            <div className="h-16 w-16 rounded-xl bg-muted flex items-center justify-center text-2xl border border-border/60">
              🚀
            </div>
          )}
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
      </CardContent>
    </Card>
  );
}
