/**
 * 自动化分类详情页面
 *
 * 未部署时：以「应用组合模板 + 流程展示」居中展示分类下的自动化流程；
 * 已部署时：以「左侧应用列表 + 右侧详情面板」管理实例组内的应用。
 */

import { Fragment, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AppIcon } from "../apps/AppIcon";
import { AutomationDeployWizard } from "./AutomationDeployWizard";
import { AutomationImportDialog } from "./AutomationImportDialog";
import { AutomationRestoreDialog } from "./AutomationRestoreDialog";
import { OrchestrationInstanceManager } from "./OrchestrationInstanceManager";
import { AppConfigPanel } from "./AppConfigPanel";
import { GROUP_LABELS, RELATION_LABELS } from "./composition-meta";
import {
  useOrchestrations,
  useOrchestrationInstances,
  useOrchestrationInstanceDetail,
  useUpdateOrchestrationInstance,
  useDeleteOrchestrationInstance,
  type AppCompositionItem,
  type AppOrchestration,
  type OrchestrationInstanceApp,
} from "@/hooks/useOrchestrations";
import { useApps, type App } from "@/hooks/useApps";
import { useDeployTasks } from "@/hooks/useDeployTasks";
import { cn } from "@/lib/utils";
import {
  ArrowRight,
  BookImage,
  BookOpen,
  Boxes,
  Film,
  Gamepad2,
  Images,
  Import,
  Loader2,
  Music,
  Newspaper,
  Rocket,
  RotateCcw,
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

interface CategoryMeta {
  icon: LucideIcon;
  description: string;
}

const CATEGORY_META: Record<string, CategoryMeta> = {
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
  appMap,
}: {
  label: string;
  category: string;
  orchestrations: AppOrchestration[];
  appMap: Record<string, App>;
}) {
  const config = CATEGORY_META[category] ?? CATEGORY_META.media;
  const Icon = config.icon;
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
  const { data: allApps = [] } = useApps();
  const appMap = Object.fromEntries(allApps.map((app) => [app.name, app]));
  const [deployOrchestration, setDeployOrchestration] =
    useState<AppOrchestration | null>(null);
  const [importOrchestration, setImportOrchestration] =
    useState<AppOrchestration | null>(null);
  const [restoreOrchestration, setRestoreOrchestration] =
    useState<AppOrchestration | null>(null);
  const [redeployId, setRedeployId] = useState<number | null>(null);
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
  const meta = CATEGORY_META[category || ""] ?? CATEGORY_META.media;

  useEffect(() => {
    setSelectedInstanceId((prev) => {
      const stillExists = instances.some((i) => i.id === prev);
      if (stillExists) return prev;
      return instances.length > 0 ? instances[0].id : null;
    });
  }, [instances]);

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
  const currentOrchestration =
    orchestrations.find(
      (o) => o.name === selectedDetail?.orchestration_name
    ) ?? null;
  const updateMutation = useUpdateOrchestrationInstance();
  const deleteMutation = useDeleteOrchestrationInstance();
  const { startTask } = useDeployTasks();

  // 详情加载后默认选中第一个应用；实例切换或应用被移除时自动修正选中项
  useEffect(() => {
    const apps = selectedDetail?.apps ?? [];
    setSelectedApp((prev) => {
      if (apps.length === 0) return null;
      if (prev && apps.some((app) => app.id === prev.id)) return prev;
      return apps[0];
    });
  }, [selectedDetail]);

  const switchInstance = (id: number) => {
    if (id === selectedInstanceId || isSwitching) return;
    setIsSwitching(true);
    if (switchTimerRef.current) {
      clearTimeout(switchTimerRef.current);
    }
    switchTimerRef.current = setTimeout(() => {
      setSelectedInstanceId(id);
      setIsSwitching(false);
    }, 120);
  };

  // 修复：加载目标实例组详情，并找到对应的编排模板
  const { data: redeployDetail } = useOrchestrationInstanceDetail(redeployId);
  const redeployOrchestration = redeployDetail
    ? (orchestrations.find((o) => o.name === redeployDetail.orchestration_name) ??
      null)
    : null;

  const hasInstances = instances.length > 0;
  const apps = selectedDetail?.apps ?? [];

  return (
    <div className="h-full flex flex-col space-y-4">
      {hasInstances && orchestrations.length > 0 ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          {/* 页面标题与操作 */}
          <div className="flex flex-wrap items-center gap-3 border-b border-border/70 px-4 py-4 sm:px-5">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10">
              <meta.icon className="h-5 w-5 text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <h1 className="text-xl font-semibold tracking-tight text-foreground">
                {`${label}自动化`}
              </h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {meta.description}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setRestoreOrchestration(orchestrations[0])}
                className="gap-1.5"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                恢复
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setImportOrchestration(orchestrations[0])}
                className="gap-1.5"
              >
                <Import className="h-3.5 w-3.5" />
                导入
              </Button>
              <Button
                size="sm"
                onClick={() => setDeployOrchestration(orchestrations[0])}
                className="gap-1.5"
              >
                <Rocket className="h-3.5 w-3.5" />
                部署
              </Button>
            </div>
          </div>

          {/* 主从布局：左侧实例组树，右侧应用详情 */}
          <div
            key={displayInstanceId ?? "empty"}
            className={cn(
              "flex flex-1 flex-col transition-opacity duration-150 ease-out lg:flex-row",
              isSwitching ? "opacity-0" : "opacity-100"
            )}
          >
            <aside className="shrink-0 border-b border-border/70 bg-muted/20 lg:flex lg:w-[288px] lg:flex-col lg:border-b-0 lg:border-r">
              <div className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
                <OrchestrationInstanceManager
                  instances={instances}
                  selectedId={selectedInstanceId}
                  selectedAppId={selectedApp?.id ?? null}
                  appMap={appMap}
                  composition={currentOrchestration?.app_composition}
                  onSelect={switchInstance}
                  onSelectApp={setSelectedApp}
                  onRename={(id, name) =>
                    updateMutation.mutate({
                      id,
                      data: { instance_name: name },
                    })
                  }
                  onDelete={(id) =>
                    deleteMutation.mutate(id, {
                      onSuccess: (response) =>
                        startTask(response.task_id),
                    })
                  }
                  onRedeploy={(id) => setRedeployId(id)}
                  isPending={
                    updateMutation.isPending || deleteMutation.isPending
                  }
                />
              </div>
            </aside>

            <section className="min-w-0 flex-1">
              {!selectedDetail || (apps.length > 0 && !selectedApp) ? (
                <div className="flex min-h-[320px] items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在加载应用…
                </div>
              ) : selectedApp ? (
                <div className="p-4 sm:p-5">
                  <AppConfigPanel
                    app={selectedApp}
                    detail={selectedDetail}
                    orchestration={currentOrchestration}
                    description={appMap[selectedApp.app_name]?.description}
                    onSave={(payload) => {
                      if (!selectedInstanceId) return;
                      updateMutation.mutate({
                        id: selectedInstanceId,
                        data: payload,
                      });
                    }}
                    isPending={updateMutation.isPending}
                  />
                </div>
              ) : (
                <div className="flex min-h-[320px] flex-col items-center justify-center gap-2 px-6 text-center">
                  <Boxes className="h-6 w-6 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">
                    该实例组暂无应用
                  </p>
                  <p className="text-xs text-muted-foreground/70">
                    可在左侧导入现有容器，或重新部署该组合。
                  </p>
                </div>
              )}
            </section>
          </div>
        </div>
      ) : (
        <Card className="rounded-xl flex-1 flex flex-col">
          <CardHeader className="flex flex-row items-start justify-between py-1 px-4 pb-0">
            <CardTitle className="text-base font-medium">
              {label}自动化
            </CardTitle>
            {orchestrations.length > 0 && (
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setRestoreOrchestration(orchestrations[0])}
                  className="gap-1.5 rounded-lg h-9"
                >
                  <RotateCcw className="h-4 w-4" />
                  恢复
                </Button>
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
            ) : (
              <OrchestrationShowcase
                label={label}
                category={category || "media"}
                orchestrations={orchestrations}
                appMap={appMap}
              />
            )}
          </CardContent>
        </Card>
      )}

      <AutomationDeployWizard
        orchestration={deployOrchestration}
        open={!!deployOrchestration}
        onOpenChange={(open) => !open && setDeployOrchestration(null)}
      />

      <AutomationDeployWizard
        orchestration={redeployOrchestration}
        open={!!redeployOrchestration}
        onOpenChange={(open) => !open && setRedeployId(null)}
        redeployGroup={redeployDetail ?? null}
      />

      <AutomationImportDialog
        orchestration={importOrchestration}
        open={!!importOrchestration}
        onOpenChange={(open) => !open && setImportOrchestration(null)}
      />

      <AutomationRestoreDialog
        orchestration={restoreOrchestration}
        open={!!restoreOrchestration}
        onOpenChange={(open) => !open && setRestoreOrchestration(null)}
      />
    </div>
  );
}
