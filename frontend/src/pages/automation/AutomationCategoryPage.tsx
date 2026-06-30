/**
 * 自动化分类详情页面
 *
 * 展示某个分类（如影视）下的应用组合模板列表。
 */

import { Fragment, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AppIcon } from "../apps/AppIcon";
import { AutomationDeployWizard } from "./AutomationDeployWizard";
import {
  useOrchestrations,
  type AppOrchestration,
  type AppCompositionItem,
} from "@/hooks/useOrchestrations";
import { useApps, type App } from "@/hooks/useApps";
import {
  ArrowRight,
  BookOpen,
  Film,
  Gamepad2,
  Images,
  Import,
  Music,
  Newspaper,
  Rocket,
  type LucideIcon,
} from "lucide-react";

const CATEGORY_LABELS: Record<string, string> = {
  media: "影视",
  comics: "漫画",
  books: "书籍",
  music: "音乐",
  games: "游戏",
  gallery: "图库",
  news: "资讯",
};

/** 应用组合关系的中文标签 */
const RELATION_LABELS: Record<AppCompositionItem["relation"], string> = {
  required: "必选",
  suggested: "推荐",
  optional: "可选",
  conflicting: "互斥",
};

/** 分组的中文标签 */
const GROUP_LABELS: Record<string, string> = {
  player: "播放器",
};

interface EmptyConfig {
  icon: LucideIcon;
  description: string;
}

const CATEGORY_EMPTY_CONFIG: Record<string, EmptyConfig> = {
  media: {
    icon: Film,
    description:
      "全流程影视自动化：搜索、下载、刮削、播放一体化，打造专属私人影库。",
  },
  comics: {
    icon: Images,
    description:
      "漫画自动化可以帮你抓取、整理、阅读漫画资源，让书架始终保持最新。",
  },
  books: {
    icon: BookOpen,
    description:
      "书籍自动化可以追踪新书上架、自动下载并整理书库，随时畅享阅读。",
  },
  music: {
    icon: Music,
    description:
      "音乐自动化可以整理曲库、抓取专辑信息并搭建流媒体服务，随时畅听。",
  },
  games: {
    icon: Gamepad2,
    description:
      "游戏自动化可以管理游戏资源、存档与相关服务，让游戏库井井有条。",
  },
  gallery: {
    icon: Images,
    description:
      "图库自动化可以整理照片、生成缩略图并提供展示页面，轻松管理回忆。",
  },
  news: {
    icon: Newspaper,
    description:
      "资讯自动化可以聚合 RSS、订阅源与文章，自动归档你关心的信息。",
  },
};

/** 流程阶段：同一 group 的应用会被合并为同一阶段（如多个播放器） */
interface Stage {
  group: string | null;
  items: AppCompositionItem[];
}

/**
 * 将应用组合按 group 合并为流程阶段：
 * 连续且 group 相同的应用归为同一阶段（如多个播放器同属"播放"环节），
 * 其余应用各自独立成阶段，按数据顺序构成自动化流程。
 */
function buildStages(composition: AppCompositionItem[]): Stage[] {
  const stages: Stage[] = [];
  for (const item of composition) {
    const last = stages[stages.length - 1];
    if (item.group && last && last.group === item.group) {
      last.items.push(item);
    } else {
      stages.push({ group: item.group ?? null, items: [item] });
    }
  }
  return stages;
}

/**
 * 判断同组应用是否互斥（二选一）：
 * 仅当组内每个应用都通过 conflict_with 与其它同组应用互斥时才成立。
 * group 本身只是分组标签，不代表互斥；可多选的分组（如播放器）不应标"二选一"。
 */
function isMutuallyExclusive(items: AppCompositionItem[]): boolean {
  if (items.length < 2) return false;
  return items.every((a) =>
    items.every(
      (b) => a === b || (a.conflict_with?.includes(b.app_name) ?? false)
    )
  );
}

function AppNode({
  item,
  appMap,
}: {
  item: AppCompositionItem;
  appMap: Record<string, App>;
}) {
  const app = appMap[item.app_name];
  return (
    <div className="flex flex-col items-center gap-2 w-20">
      {app ? (
        <AppIcon
          app={app}
          className="h-14 w-14 rounded-[22%] object-cover shadow-md"
        />
      ) : (
        <div className="h-14 w-14 rounded-[22%] bg-gradient-to-br from-primary/15 to-primary/5 flex items-center justify-center text-2xl shadow-md">
          🚀
        </div>
      )}
      <span className="text-xs font-medium text-foreground/80 text-center leading-tight line-clamp-2">
        {app?.display_name || item.app_name}
      </span>
    </div>
  );
}

function StageFlow({
  composition,
  appMap,
}: {
  composition: AppCompositionItem[];
  appMap: Record<string, App>;
}) {
  const stages = buildStages(composition);

  return (
    <div className="flex flex-wrap items-start justify-center gap-x-3 gap-y-6 sm:gap-x-4">
      {stages.map((stage, index) => {
        const isRequired =
          !stage.group && stage.items[0]?.relation === "required";
        const mutex = isMutuallyExclusive(stage.items);
        const caption = stage.group
          ? `${GROUP_LABELS[stage.group] ?? stage.group} · ${
              mutex ? "二选一" : "可选"
            }`
          : RELATION_LABELS[stage.items[0]?.relation] ?? "可选";

        return (
          <Fragment key={`${stage.group ?? "single"}-${index}`}>
            {index > 0 && (
              <ArrowRight className="h-4 w-4 shrink-0 self-start mt-5 text-muted-foreground/40" />
            )}
            <div className="flex flex-col items-center gap-2.5">
              <div className="flex items-start gap-2.5">
                {stage.items.map((item, itemIndex) => (
                  <Fragment key={item.app_name}>
                    {itemIndex > 0 && (
                      <span className="self-start mt-5 text-[11px] font-medium text-muted-foreground/60">
                        或
                      </span>
                    )}
                    <AppNode item={item} appMap={appMap} />
                  </Fragment>
                ))}
              </div>
              <span
                className={`text-[11px] leading-none ${
                  isRequired ? "text-primary/70" : "text-muted-foreground"
                }`}
              >
                {caption}
              </span>
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}

function OrchestrationShowcase({
  label,
  category,
  orchestrations,
  onDeploy,
}: {
  label: string;
  category: string;
  orchestrations: AppOrchestration[];
  onDeploy: (orchestration: AppOrchestration) => void;
}) {
  const config = CATEGORY_EMPTY_CONFIG[category] ?? CATEGORY_EMPTY_CONFIG.media;
  const Icon = config.icon;
  const { data: allApps = [] } = useApps();
  const appMap = Object.fromEntries(allApps.map((app) => [app.name, app]));
  const multiple = orchestrations.length > 1;

  return (
    <div className="relative flex-1 flex flex-col px-6 py-8 overflow-y-auto">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[360px] h-[360px] rounded-full bg-primary/[0.04] blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto mt-16 mb-auto flex flex-col items-center text-center max-w-3xl w-full">
        <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 flex items-center justify-center mb-5 shadow-sm ring-1 ring-primary/10">
          <Icon className="h-10 w-10 text-primary" />
        </div>

        <h3 className="text-lg font-semibold text-foreground">{label}自动化</h3>
        <p className="text-sm text-muted-foreground mt-2 leading-relaxed max-w-lg">
          {config.description}
        </p>

        <div className="mt-8 w-full flex flex-col items-center gap-10">
          {orchestrations.map((orchestration) => (
            <div
              key={orchestration.name}
              className="group w-full flex flex-col items-center gap-5"
            >
              {multiple && (
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-foreground">
                    {orchestration.display_name}
                  </h4>
                  {orchestration.description && (
                    <p className="text-xs text-muted-foreground max-w-md">
                      {orchestration.description}
                    </p>
                  )}
                </div>
              )}

              <StageFlow
                composition={orchestration.app_composition}
                appMap={appMap}
              />

              <div className="flex items-center justify-between w-full max-w-lg mt-2 px-8">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    // TODO: 接入已有 Docker 部署
                    console.log("导入已有部署", orchestration.name)
                  }
                  className="gap-2 rounded-lg px-5 h-10 text-sm font-medium border-primary/30 text-primary hover:bg-primary/5 hover:border-primary/50 transition-colors"
                >
                  <Import className="h-4 w-4 transition-transform group-hover/button:-translate-y-0.5" />
                  导入
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onDeploy(orchestration)}
                  className="gap-2 rounded-lg px-5 h-10 text-sm font-medium border-primary/30 text-primary hover:bg-primary/5 hover:border-primary/50 transition-colors"
                >
                  部署
                  <Rocket className="h-4 w-4 transition-transform group-hover/button:-translate-y-0.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function AutomationCategoryPage() {
  const { category } = useParams<{ category: string }>();
  const { data: orchestrations = [], isLoading } = useOrchestrations(category);
  const [deployOrchestration, setDeployOrchestration] =
    useState<AppOrchestration | null>(null);

  const label = CATEGORY_LABELS[category || ""] || category || "自动化";

  return (
    <div className="h-full flex flex-col space-y-4">
      <Card className="rounded-xl flex-1 flex flex-col">
        <CardContent className="flex-1 flex flex-col p-4">
          {isLoading ? (
            <div className="text-sm text-muted-foreground py-12 text-center">
              加载中...
            </div>
          ) : orchestrations.length === 0 ? (
            <div className="text-sm text-muted-foreground py-12 text-center">
              暂无 {label} 自动化组合模板
            </div>
          ) : (
            <OrchestrationShowcase
              label={label}
              category={category || "media"}
              orchestrations={orchestrations}
              onDeploy={setDeployOrchestration}
            />
          )}
        </CardContent>
      </Card>

      <AutomationDeployWizard
        orchestration={deployOrchestration}
        open={!!deployOrchestration}
        onOpenChange={(open) => !open && setDeployOrchestration(null)}
      />
    </div>
  );
}
