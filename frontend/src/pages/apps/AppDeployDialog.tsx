/**
 * 应用部署弹窗
 *
 * 上下布局：上方为配置表单，下方实时展示渲染后的 Compose YAML。
 */

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SchemaForm } from "@/components/SchemaForm";
import { CodeBlock } from "@/components/ui/code-block";
import { useToast } from "@/components/ui/toast";
import { getApp } from "@/api/apps";
import { getImageTags } from "@/api/docker";
import { sanitizeInstanceName, slugify } from "@/lib/utils";
import {
  extractDefaults,
  fillEmptyPasswords,
} from "@/lib/schema-utils";
import { useAppPreview, type AppPreviewRequest } from "@/hooks/useApps";
import type { App } from "@/hooks/useApps";
import type { SchemaProperty } from "@/components/SchemaForm";

interface AppDeployDialogProps {
  app: App | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeploy: (data: {
    instance_name: string;
    config: Record<string, unknown>;
  }) => void;
  isDeploying?: boolean;
}

function useDebouncedPreview(
  app: App | null,
  instanceName: string,
  config: Record<string, unknown>
) {
  const preview = useAppPreview(app?.name || "");
  const [yaml, setYaml] = useState("<初始化预览中…>");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!app) return;

    const timer = setTimeout(() => {
      const payload: AppPreviewRequest = {
        instance_name: slugify(instanceName) || slugify(app.display_name),
        config,
      };
      preview.mutate(payload, {
        onSuccess: (data) => {
          if (data.error) {
            setError(data.error);
            setYaml("");
          } else {
            setYaml(data.yaml || "");
            setError(null);
          }
        },
        onError: () => {
          setError("预览请求失败");
          setYaml("");
        },
      });
    }, 500);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [app?.name, instanceName, JSON.stringify(config)]);

  return { yaml, error, isPending: preview.isPending };
}

export function AppDeployDialog({
  app: propApp,
  open,
  onOpenChange,
  onDeploy,
  isDeploying = false,
}: AppDeployDialogProps) {
  // 弹窗内直接请求最新应用详情，不依赖任何缓存
  const [app, setApp] = useState<App | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState(false);
  const [fetchErrorMessage, setFetchErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !propApp?.name) {
      setApp(null);
      setFetchError(false);
      setFetchErrorMessage(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setFetchError(false);
    setFetchErrorMessage(null);

    getApp(propApp.name, controller.signal)
      .then((appDetail) => {
        setApp(appDetail);
      })
      .catch((err) => {
        if (err?.code !== "ERR_CANCELED") {
          setFetchError(true);
          setFetchErrorMessage(
            err?.displayMessage || err?.message || "请求失败"
          );
          console.error("获取应用详情失败:", err);
        }
      })
      .finally(() => {
        setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [open, propApp?.name]);

  // 打开时随应用变化重置表单
  const [instanceName, setInstanceName] = useState("");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [imageTags, setImageTags] = useState<string[]>([]);
  const [imageTagsLoading, setImageTagsLoading] = useState(false);

  const appDisplayName = app?.display_name || "";
  const appConfigSchema = app?.config_schema || {};

  useEffect(() => {
    setInstanceName(slugify(appDisplayName));
    const defaults = extractDefaults(appConfigSchema);
    setConfig(fillEmptyPasswords(appConfigSchema, defaults));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appDisplayName, JSON.stringify(appConfigSchema)]);

  // 获取镜像可用标签列表
  const appImage = app?.image;
  useEffect(() => {
    if (!appImage) {
      setImageTags([]);
      return;
    }

    const controller = new AbortController();
    setImageTagsLoading(true);

    getImageTags(appImage, controller.signal)
      .then((tags) => {
        setImageTags(tags.map((tag) => tag.name));
      })
      .catch(() => {
        setImageTags([]);
      })
      .finally(() => {
        setImageTagsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [appImage]);

  const toast = useToast();

  const { yaml, error, isPending } = useDebouncedPreview(app, instanceName, config);

  if (!open || !propApp) return null;

  if (loading) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="px-6 pt-5 pb-3 flex-shrink-0">
            <DialogTitle>加载中…</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 px-6 py-8 flex items-center justify-center">
            <p className="text-sm text-muted-foreground">正在加载应用配置</p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  if (fetchError || !app) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="px-6 pt-5 pb-3 flex-shrink-0">
            <DialogTitle>加载失败</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 px-6 py-8 flex flex-col items-center justify-center gap-2">
            <p className="text-sm text-muted-foreground">无法获取应用详情，请刷新页面重试</p>
            {fetchErrorMessage && (
              <p className="text-xs text-destructive max-w-md text-center break-all">
                {fetchErrorMessage}
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  const handleDeploy = () => {
    const projectName = slugify(instanceName);
    if (!projectName) {
      toast.error("请输入有效的实例名称");
      return;
    }
    onDeploy({ instance_name: projectName, config });
  };

  return (
    <Dialog key={app.name} open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-3 flex-shrink-0">
          <DialogTitle>部署 {app.display_name}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 min-h-0 px-6 py-3 overflow-y-auto scrollbar-thin">
          <div className="flex flex-col gap-5">
            {/* 配置表单 */}
            <div className="flex flex-col gap-4 pr-1">
              <div className="space-y-1">
                <Label htmlFor="instance-name" className="text-xs font-medium">
                  实例名称
                  <span className="ml-0.5 text-destructive" aria-hidden="true">*</span>
                </Label>
                <Input
                  id="instance-name"
                  value={instanceName}
                  onChange={(e) => setInstanceName(sanitizeInstanceName(e.target.value))}
                  onBlur={() => setInstanceName(slugify(instanceName))}
                  placeholder="如：my-moviepilot"
                  className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
                />
              </div>

              <SchemaForm
                schema={
                  app.config_schema as {
                    properties?: Record<string, SchemaProperty>;
                    required?: string[];
                  }
                }
                data={config}
                onChange={setConfig}
                instanceName={instanceName}
                image={app.image || ""}
                imageTags={imageTags}
                imageTagsLoading={imageTagsLoading}
              />
            </div>

            {/* Compose 预览 */}
            <div className="flex flex-col">
              <div className="mb-2">
                <h4 className="text-sm font-semibold">docker-compose.yml 预览</h4>
                <p className="text-xs text-muted-foreground">
                  根据上方配置实时渲染，部署前可确认最终内容
                </p>
              </div>
              <CodeBlock
                code={error || yaml}
                emptyText="加载预览中…"
                language="yaml"
              />
              {error && (
                <p className="mt-2 text-xs text-destructive">
                  预览生成失败：{error}
                </p>
              )}
              {isPending && !error && (
                <p className="mt-2 text-xs text-muted-foreground">更新预览中…</p>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 px-6 py-3 border-t flex-shrink-0">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isDeploying}
          >
            取消
          </Button>
          <Button onClick={handleDeploy} disabled={isDeploying}>
            {isDeploying ? "部署中…" : "一键部署"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
