/**
 * 编排实例组应用卡片网格
 *
 * 展示某个实例组下的所有应用实例，支持点击选中。
 */

import { Card } from "@/components/ui/card";
import { AppIcon } from "../apps/AppIcon";
import type { App } from "@/hooks/useApps";
import type { OrchestrationInstanceApp } from "@/hooks/useOrchestrations";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface AppInstanceGridProps {
  apps: OrchestrationInstanceApp[];
  selectedAppId: number | null;
  onSelectApp: (app: OrchestrationInstanceApp) => void;
}

const STATUS_COLORS: Record<string, string> = {
  running: "bg-emerald-500/15 text-emerald-600",
  stopped: "bg-muted text-muted-foreground",
  error: "bg-destructive/15 text-destructive",
  deploying: "bg-primary/15 text-primary",
};

export function AppInstanceGrid({
  apps,
  selectedAppId,
  onSelectApp,
}: AppInstanceGridProps) {
  if (apps.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/50 p-8 text-center">
        <p className="text-sm text-muted-foreground">该实例组暂无应用</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      {apps.map((app) => {
        const isSelected = selectedAppId === app.id;
        const status = app.status || "stopped";
        return (
          <Card
            key={app.id}
            className={cn(
              "group relative overflow-hidden rounded-2xl cursor-pointer transition-all duration-300",
              "hover:-translate-y-1 hover:shadow-lg",
              "border bg-gradient-to-br from-card to-muted/20",
              isSelected
                ? "border-primary/40 bg-primary/[0.03] ring-1 ring-primary/30 shadow-sm"
                : "border-border/60 shadow-[0_1px_3px_rgba(0,0,0,0.05)]"
            )}
            onClick={() => onSelectApp(app)}
          >
            {/* 悬停背景渐变 */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.03] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

            {/* 选中勾选标记 */}
            {isSelected && (
              <div className="absolute top-3 right-3 h-5 w-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-sm">
                <Check className="h-3 w-3" />
              </div>
            )}

            <div className="relative flex flex-col items-center gap-3 p-5">
              {/* 图标 + 状态点 */}
              <div className="relative">
                <AppIcon
                  app={
                    {
                      name: app.app_name,
                      display_name: app.display_name,
                      icon: app.icon,
                    } as App
                  }
                  className="h-14 w-14 rounded-[26%] object-cover shadow-md ring-1 ring-foreground/5"
                />
                <div
                  className={cn(
                    "absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-2 border-card",
                    status === "running"
                      ? "bg-emerald-500"
                      : status === "error"
                      ? "bg-destructive"
                      : status === "deploying"
                      ? "bg-primary"
                      : "bg-muted-foreground/40"
                  )}
                />
              </div>

              {/* 名称与状态 */}
              <div className="flex flex-col items-center gap-1.5 w-full">
                <span className="text-sm font-semibold text-center line-clamp-1 text-foreground">
                  {app.display_name}
                </span>
                <span
                  className={cn(
                    "text-[10px] px-2 py-0.5 rounded-full font-medium capitalize tracking-wide",
                    STATUS_COLORS[status] ?? "bg-muted text-muted-foreground"
                  )}
                >
                  {status}
                </span>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
