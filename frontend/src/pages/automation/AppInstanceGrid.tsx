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
      {apps.map((app) => (
        <Card
          key={app.id}
          className={cn(
            "group relative flex flex-col items-center gap-3 p-4 cursor-pointer transition-all",
            "hover:border-primary/40 hover:shadow-sm",
            selectedAppId === app.id
              ? "border-primary/60 bg-primary/[0.02] ring-1 ring-primary/20"
              : "border-border bg-card"
          )}
          onClick={() => onSelectApp(app)}
        >
          <AppIcon
            app={
              {
                name: app.app_name,
                display_name: app.display_name,
                icon: app.icon,
              } as App
            }
            className="h-14 w-14 rounded-[22%] object-cover shadow-sm"
          />
          <div className="flex flex-col items-center gap-1 w-full">
            <span className="text-sm font-medium text-center line-clamp-1">
              {app.display_name}
            </span>
            <span
              className={cn(
                "text-[10px] px-2 py-0.5 rounded-full capitalize",
                STATUS_COLORS[app.status] ??
                  "bg-muted text-muted-foreground"
              )}
            >
              {app.status}
            </span>
          </div>
        </Card>
      ))}
    </div>
  );
}
