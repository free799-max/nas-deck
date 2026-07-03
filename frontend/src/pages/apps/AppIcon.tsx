/**
 * 应用图标组件
 *
 * 仅当 `icon` 为外链时直接使用，否则回退到前端静态资源
 * `/icons/apps/<name>.svg`，加载失败时显示火箭占位。
 */

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { App } from "@/hooks/useApps";

interface AppIconProps {
  app: App;
  className?: string;
}

export function AppIcon({ app, className }: AppIconProps) {
  const [failed, setFailed] = useState(false);

  const src = app.icon?.startsWith("http")
    ? app.icon
    : `/icons/apps/${app.name}.svg`;

  if (failed) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-[22%] bg-gradient-to-br from-primary/15 to-primary/5 text-2xl",
          className
        )}
      >
        🚀
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-[22%] bg-white",
        className
      )}
    >
      <img
        src={src}
        alt={app.display_name}
        className="h-full w-full object-contain"
        onError={() => setFailed(true)}
      />
    </div>
  );
}
