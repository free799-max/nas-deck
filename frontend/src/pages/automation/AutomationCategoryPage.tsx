/**
 * 自动化分类详情页面
 *
 * 展示某个分类（如影视）下的应用组合模板列表。
 */

import { Fragment, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AppIcon } from "../apps/AppIcon";
import { AutomationDeployWizard } from "./AutomationDeployWizard";
import { AutomationImportDialog } from "./AutomationImportDialog";
import { OrchestrationInstanceManager } from "./OrchestrationInstanceManager";
import { AppInstanceGrid } from "./AppInstanceGrid";
import { AppConfigPanel } from "./AppConfigPanel";
import {
  useOrchestrations,
  useOrchestrationInstances,
  useOrchestrationInstanceDetail,
  useUpdateOrchestrationInstance,
  useDeleteOrchestrationInstance,
  type AppOrchestration,
  type AppCompositionItem,
  type OrchestrationInstanceApp,
} from "@/hooks/useOrchestrations";
import { useApps, type App } from "@/hooks/useApps";
import { cn } from "@/lib/utils";
import {
  ArrowRight,
  BookImage,
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
    icon: BookImage,
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
}: {
  label: string;
  category: string;
  orchestrations: AppOrchestration[];
}) {
  const config = CATEGORY_EMPTY_CONFIG[category] ?? CATEGORY_EMPTY_CONFIG.media;
  const Icon = config.icon;
  const { data: allApps = [] } = useApps();
  const appMap = Object.fromEntries(allApps.map((app) => [app.name, app]));
  const multiple = orchestrations.length > 1;
  const isEmpty = orchestrations.length === 0;

  return (
    <div className="relative flex-1 flex flex-col px-6 pt-20 pb-8 overflow-y-auto">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[360px] h-[360px] rounded-full bg-primary/[0.04] blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto mt-16 flex flex-col items-center text-center max-w-3xl w-full">
        <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 flex items-center justify-center mb-5 shadow-sm ring-1 ring-primary/10">
          <Icon className="h-10 w-10 text-primary" />
        </div>

        <h3 className="text-lg font-semibold text-foreground">{label}自动化</h3>
        <p className="text-sm text-muted-foreground mt-2 leading-relaxed max-w-lg">
          {isEmpty ? `暂无 ${label} 自动化组合模板` : config.description}
        </p>

        {!isEmpty && (
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
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AutomationCategoryPage() {
  const { category } = useParams<{ category: string }>();
  const { data: orchestrations = [], isLoading } = useOrchestrations(category);
  const { data: instances = [] } = useOrchestrationInstances(category);
  const [deployOrchestration, setDeployOrchestration] =
    useState<AppOrchestration | null>(null);
  const [importOrchestration, setImportOrchestration] =
    useState<AppOrchestration | null>(null);
  const [selectedInstanceId, setSelectedInstanceId] = useState<number | null>(
    null
  );
  const [selectedApp, setSelectedApp] =
    useState<OrchestrationInstanceApp | null>(null);
  const [displayInstanceId, setDisplayInstanceId] = useState<number | null>(
    null
  );
  const [isSwitching, setIsSwitching] = useState(false);
  const switchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const label = CATEGORY_LABELS[category || ""] || category || "自动化";

  useEffect(() => {
    setSelectedInstanceId((prev) => {
      const stillExists = instances.some((i) => i.id === prev);
      if (stillExists) return prev;
      return instances.length > 0 ? instances[0].id : null;
    });
  }, [instances]);

  useEffect(() => {
    setSelectedApp(null);
  }, [selectedInstanceId]);

  useEffect(() => {
    setDisplayInstanceId(selectedInstanceId);
  }, [selectedInstanceId]);

  useEffect(() => {
    return () => {
      if (switchTimerRef.current) {
        clearTimeout(switchTimerRef.current);
      }
    };
  }, []);

  const { data: selectedDetail } = useOrchestrationInstanceDetail(
    displayInstanceId
  );
  const updateMutation = useUpdateOrchestrationInstance();
  const deleteMutation = useDeleteOrchestrationInstance();

  const hasInstances = instances.length > 0;

  return (
    <div className="h-full flex flex-col space-y-4">
      <Card className="rounded-xl flex-1 flex flex-col">
        <CardHeader className="flex flex-row items-start justify-between py-1 px-4 pb-0">
          <CardTitle className="text-base font-medium">{label}自动化</CardTitle>
          {orchestrations.length > 0 && (
            <div className="flex items-center gap-2">
              <OrchestrationInstanceManager
                instances={instances}
                selectedId={selectedInstanceId}
                onSelect={(id) => {
                  if (id === selectedInstanceId || isSwitching) return;
                  setIsSwitching(true);
                  if (switchTimerRef.current) {
                    clearTimeout(switchTimerRef.current);
                  }
                  switchTimerRef.current = setTimeout(() => {
                    setSelectedInstanceId(id);
                    setIsSwitching(false);
                  }, 120);
                }}
                onRename={(id, name) =>
                  updateMutation.mutate({ id, data: { instance_name: name } })
                }
                onDelete={(id) => deleteMutation.mutate(id)}
                isPending={
                  updateMutation.isPending || deleteMutation.isPending
                }
              />
              <div className="h-5 w-px bg-border" />
              <Button
                size="sm"
                variant="outline"
                onClick={() => setImportOrchestration(orchestrations[0])}
                className="gap-1.5 rounded-lg h-9"
              >
                <Import className="h-4 w-4" />
                导入
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setDeployOrchestration(orchestrations[0])}
                className="gap-1.5 rounded-lg h-9"
              >
                <Rocket className="h-4 w-4" />
                部署
              </Button>
            </div>
          )}
        </CardHeader>

        <CardContent className="flex-1 flex flex-col px-4 pb-4 pt-0 overflow-y-auto">
          {isLoading ? (
            <div className="text-sm text-muted-foreground py-12 text-center">
              加载中…
            </div>
          ) : orchestrations.length === 0 ? (
            <OrchestrationShowcase
              label={label}
              category={category || "media"}
              orchestrations={[]}
            />
          ) : !hasInstances ? (
            <OrchestrationShowcase
              label={label}
              category={category || "media"}
              orchestrations={orchestrations}
            />
          ) : (
            <div
              key={displayInstanceId ?? "empty"}
              className={cn(
                "space-y-4 pt-1 transition-opacity duration-150 ease-out",
                isSwitching ? "opacity-0" : "opacity-100"
              )}
            >
              <AppInstanceGrid
                apps={selectedDetail?.apps ?? []}
                selectedAppId={selectedApp?.id ?? null}
                onSelectApp={setSelectedApp}
              />

              <AppConfigPanel
                app={selectedApp}
                detail={selectedDetail}
                onSave={(payload) => {
                  if (!selectedInstanceId) return;
                  updateMutation.mutate({ id: selectedInstanceId, data: payload });
                }}
                isPending={updateMutation.isPending}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <AutomationDeployWizard
        orchestration={deployOrchestration}
        open={!!deployOrchestration}
        onOpenChange={(open) => !open && setDeployOrchestration(null)}
      />

      <AutomationImportDialog
        orchestration={importOrchestration}
        open={!!importOrchestration}
        onOpenChange={(open) => !open && setImportOrchestration(null)}
      />
    </div>
  );
}
