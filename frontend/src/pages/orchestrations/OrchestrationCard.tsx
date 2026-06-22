/**
 * 编排卡片组件
 *
 * 应用商店风格：左侧图标、中间信息、右侧安装按钮。
 */

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AppOrchestration } from "@/hooks/useOrchestrations";

interface OrchestrationCardProps {
  orchestration: AppOrchestration;
  onDeploy: (orchestration: AppOrchestration) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  web: "网站",
  media: "多媒体",
  database: "数据库",
  ai: "AI",
  devops: "DevOps",
  tools: "实用工具",
  storage: "云存储",
  security: "安全",
  middleware: "中间件",
  runtime: "运行环境",
  devtools: "开发工具",
  bi: "BI",
  crm: "CRM",
  email: "邮件服务",
};

function getCategoryLabel(category: string) {
  return CATEGORY_LABELS[category] ?? category;
}

export function OrchestrationCard({ orchestration, onDeploy }: OrchestrationCardProps) {
  return (
    <Card className="rounded-xl p-5 hover:shadow-[0_4px_12px_rgba(0,0,0,0.05)] transition-shadow">
      <CardContent className="p-0 flex items-center gap-5">
        {/* 图标 */}
        <div className="shrink-0">
          {orchestration.icon ? (
            <img
              src={
                orchestration.icon.startsWith("http")
                  ? orchestration.icon
                  : `/api/orchestrations/${orchestration.name}/icon`
              }
              alt={orchestration.display_name}
              className="h-14 w-14 rounded-xl object-contain bg-white border border-border/60"
            />
          ) : (
            <div className="h-14 w-14 rounded-xl bg-muted flex items-center justify-center text-2xl border border-border/60">
              🚀
            </div>
          )}
        </div>

        {/* 信息区 */}
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-foreground truncate">
            {orchestration.display_name}
          </h3>
          <p className="text-sm text-muted-foreground line-clamp-1 mt-0.5">
            {orchestration.description || "暂无描述"}
          </p>
          <div className="mt-2.5">
            <Badge
              variant="secondary"
              className="text-xs font-normal bg-[#f5f5f5] text-muted-foreground hover:bg-[#f5f5f5]"
            >
              {getCategoryLabel(orchestration.category)}
            </Badge>
          </div>
        </div>

        {/* 安装按钮 */}
        <div className="shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDeploy(orchestration)}
            className="rounded-full px-5 border-[#1a5aff]/30 text-[#1a5aff] hover:bg-[#1a5aff]/5 hover:text-[#1a5aff] hover:border-[#1a5aff]/40"
          >
            安装
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
