/**
 * 自动化分类详情页面
 *
 * 未部署时：以「模板卡片 + 流水线可视化」展示分类下的应用组合模板；
 * 已部署时：以「左侧应用列表 + 右侧详情面板」管理实例组内的应用。
 */

import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
import { AutomationDeployWizard } from "./AutomationDeployWizard";
import { AutomationImportDialog } from "./AutomationImportDialog";
import { OrchestrationInstanceManager } from "./OrchestrationInstanceManager";
import { OrchestrationPipeline } from "./OrchestrationPipeline";
import { AppConfigPanel } from "./AppConfigPanel";
import {
  useOrchestrations,
  useOrchestrationInstances,
  useOrchestrationInstanceDetail,
  useUpdateOrchestrationInstance,
  useDeleteOrchestrationInstance,
  type AppOrchestration,
  type OrchestrationInstanceApp,
} from "@/hooks/useOrchestrations";
import { useApps, type App } from "@/hooks/useApps";
import { cn } from "@/lib/utils";
import {
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

/** 编排模板卡片：头部为模板信息与操作，主体为应用组合流水线 */
function OrchestrationTemplateCard({
  orchestration,
  appMap,
  onDeploy,
  onImport,
}: {
  orchestration: AppOrchestration;
  appMap: Record<string, App>;
  onDeploy: (orchestration: AppOrchestration) => void;
  onImport: (orchestration: AppOrchestration) => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-start gap-4">
        {orchestration.icon ? (
          <img
            src={
              orchestration.icon.startsWith("http")
                ? orchestration.icon
                : `/api/orchestrations/${orchestration.name}/icon`
            }
            alt={orchestration.display_name}
            className="h-12 w-12 shrink-0 rounded-xl border border-border/60 bg-white object-contain"
          />
        ) : (
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-gradient-to-br from-primary/15 to-primary/5">
            <Rocket className="h-5 w-5 text-primary" />
          </div>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">
              {orchestration.display_name}
            </h3>
            {orchestration.tags.slice(0, 3).map((tag) => (
              <Badge
                key={tag}
                variant="secondary"
                className="max-w-[80px] truncate text-xs font-normal"
              >
                {tag}
              </Badge>
            ))}
          </div>
          {orchestration.description && (
            <p className="mt-1 text-sm text-muted-foreground">
              {orchestration.description}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5"
            onClick={() => onImport(orchestration)}
          >
            <Import className="h-3.5 w-3.5" />
            导入现有
          </Button>
          <Button
            size="sm"
            className="gap-1.5"
            onClick={() => onDeploy(orchestration)}
          >
            <Rocket className="h-3.5 w-3.5" />
            立即部署
          </Button>
        </div>
      </div>

      <div className="mt-4 border-t border-border/60 pt-4">
        <OrchestrationPipeline
          composition={orchestration.app_composition}
          appMap={appMap}
        />
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
  const showPageHeader = !hasInstances || orchestrations.length === 0;

  return (
    <div className="h-full flex flex-col">
      {showPageHeader && (
        <PageHeader
          title={`${label}自动化`}
          description={meta.description}
          icon={meta.icon}
        />
      )}

      <div className="flex-1 min-h-0 overflow-y-auto">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">
            加载中…
          </div>
        ) : orchestrations.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10">
              <meta.icon className="h-8 w-8 text-primary" />
            </div>
            <p className="text-sm text-muted-foreground">
              暂无{label}自动化组合模板
            </p>
          </div>
        ) : !hasInstances ? (
          <div className="flex flex-col gap-4">
            {orchestrations.map((orchestration) => (
              <OrchestrationTemplateCard
                key={orchestration.name}
                orchestration={orchestration}
                appMap={appMap}
                onDeploy={setDeployOrchestration}
                onImport={setImportOrchestration}
              />
            ))}
          </div>
        ) : (
          <div className="flex min-h-full flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
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
                    onDelete={(id) => deleteMutation.mutate(id)}
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
        )}
      </div>

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
    </div>
  );
}
