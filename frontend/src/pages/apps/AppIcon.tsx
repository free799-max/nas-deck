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
      <div className={cn("flex items-center justify-center", className)}>
        <span className="leading-none">🚀</span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={app.display_name}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
