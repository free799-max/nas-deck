/**
 * 应用配置面板
 *
 * 展示选中应用的访问地址，并提供设置入口弹出认证配置弹窗。
 */

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Save, Settings, Shield } from "lucide-react";
import type {
  OrchestrationInstanceApp,
  OrchestrationInstanceDetail,
  OrchestrationInstanceUpdatePayload,
} from "@/hooks/useOrchestrations";

interface AppConfigPanelProps {
  app: OrchestrationInstanceApp | null;
  detail: OrchestrationInstanceDetail | null | undefined;
  onSave: (payload: OrchestrationInstanceUpdatePayload) => void;
  isPending?: boolean;
}

const AUTH_TYPE_LABELS: Record<"none" | "basic" | "apikey", string> = {
  none: "无认证",
  basic: "账号密码",
  apikey: "API Key",
};

interface AppAuthConfig {
  url?: string;
  auth_type?: "none" | "basic" | "apikey";
  username?: string;
  password?: string;
  api_key?: string;
}

function getInitialAuthConfig(raw: unknown): AppAuthConfig {
  const config = (raw ?? {}) as Record<string, unknown>;
  const authType = ["none", "basic", "apikey"].includes(String(config.auth_type))
    ? (String(config.auth_type) as "none" | "basic" | "apikey")
    : "none";
  return {
    url: typeof config.url === "string" ? config.url : "",
    auth_type: authType,
    username: typeof config.username === "string" ? config.username : "",
    password: typeof config.password === "string" ? config.password : "",
    api_key: typeof config.api_key === "string" ? config.api_key : "",
  };
}

function buildAuthConfig(values: AppAuthConfig): Record<string, unknown> {
  const config: Record<string, unknown> = {
    url: values.url?.trim() || "",
    auth_type: values.auth_type,
  };
  if (values.auth_type === "basic") {
    config.username = values.username?.trim() || "";
    config.password = values.password || "";
  } else if (values.auth_type === "apikey") {
    config.api_key = values.api_key?.trim() || "";
  }
  return config;
}

export function AppConfigPanel({
  app,
  detail,
  onSave,
  isPending = false,
}: AppConfigPanelProps) {
  const [authConfig, setAuthConfig] = useState<AppAuthConfig>(
    getInitialAuthConfig(detail?.app_configs?.[app?.app_name ?? ""])
  );
  const [dialogOpen, setDialogOpen] = useState(false);
  const [draft, setDraft] = useState<AppAuthConfig>(authConfig);

  useEffect(() => {
    const next = getInitialAuthConfig(detail?.app_configs?.[app?.app_name ?? ""]);
    setAuthConfig(next);
    setDraft(next);
  }, [detail, app]);

  if (!app || !detail) {
    return null;
  }

  const handleOpen = () => {
    setDraft({ ...authConfig });
    setDialogOpen(true);
  };

  const handleSave = () => {
    onSave({
      shared_config: {},
      app_configs: {
        ...detail.app_configs,
        [app.app_name]: buildAuthConfig(draft),
      },
    });
    setDialogOpen(false);
  };

  const url = authConfig.url?.trim() || "";
  const isValidUrl =
    url.startsWith("http://") || url.startsWith("https://");

  return (
    <>
      <div className="mt-4 rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Settings className="h-4 w-4" />
            应用配置（{app.app_name}）
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          {isValidUrl ? (
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-primary hover:underline truncate"
            >
              {url}
            </a>
          ) : (
            <span className="text-sm text-muted-foreground truncate">
              {url || "未配置访问地址"}
            </span>
          )}

          <Button
            size="icon-sm"
            variant="ghost"
            className="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground"
            onClick={handleOpen}
            disabled={isPending}
            title="认证设置"
          >
            <Shield className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>配置 {app.display_name}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="flex items-center gap-3">
              <Label htmlFor="config-url" className="shrink-0 text-sm">访问地址</Label>
              <Input
                id="config-url"
                value={draft.url}
                onChange={(e) =>
                  setDraft((prev) => ({ ...prev, url: e.target.value }))
                }
                placeholder="http://192.168.1.1:3000"
              />
            </div>

            <div className="space-y-2">
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    ["none", AUTH_TYPE_LABELS.none],
                    ["basic", AUTH_TYPE_LABELS.basic],
                    ["apikey", AUTH_TYPE_LABELS.apikey],
                  ] as const
                ).map(([type, label]) => (
                  <Button
                    key={type}
                    type="button"
                    variant={draft.auth_type === type ? "default" : "outline"}
                    size="sm"
                    className="h-8 text-xs"
                    onClick={() =>
                      setDraft((prev) => ({
                        ...prev,
                        auth_type: type,
                      }))
                    }
                  >
                    {label}
                  </Button>
                ))}
              </div>
            </div>

            {draft.auth_type === "basic" && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="config-username" className="text-sm">用户名</Label>
                  <Input
                    id="config-username"
                    value={draft.username}
                    onChange={(e) =>
                      setDraft((prev) => ({
                        ...prev,
                        username: e.target.value,
                      }))
                    }
                    placeholder="admin"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="config-password" className="text-sm">密码</Label>
                  <Input
                    id="config-password"
                    type="password"
                    value={draft.password}
                    onChange={(e) =>
                      setDraft((prev) => ({
                        ...prev,
                        password: e.target.value,
                      }))
                    }
                    placeholder="••••••"
                  />
                </div>
              </div>
            )}

            {draft.auth_type === "apikey" && (
              <div className="space-y-1.5">
                <Label htmlFor="config-api-key" className="text-sm">API Key</Label>
                <Input
                  id="config-api-key"
                  type="password"
                  value={draft.api_key}
                  onChange={(e) =>
                    setDraft((prev) => ({
                      ...prev,
                      api_key: e.target.value,
                    }))
                  }
                  placeholder="请输入 API Key"
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              disabled={isPending}
            >
              取消
            </Button>
            <Button onClick={handleSave} disabled={isPending}>
              {isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="mr-1.5 h-3.5 w-3.5" />
              )}
              保存配置
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
