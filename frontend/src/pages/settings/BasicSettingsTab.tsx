/**
 * 基础配置 Tab
 *
 * 包含代理配置、服务端口与统一服务账号：
 * - 代理：HTTP/HTTPS/No Proxy
 * - 服务端口：服务起始端口
 * - 统一服务账号：编排部署时自动配置到各服务
 * 存储相关配置见「存储配置」Tab。
 */

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useSystemConfig, useUpdateSystemConfig } from "@/hooks/useSettings";
import { Network, Plug, KeyRound } from "lucide-react";

interface BasicFormState {
  http_proxy: string;
  https_proxy: string;
  no_proxy: string;
  service_port_start: number;
  default_admin_username: string;
  default_admin_password: string;
}

/** 空表单 */
const EMPTY_FORM: BasicFormState = {
  http_proxy: "",
  https_proxy: "",
  no_proxy: "",
  service_port_start: 10000,
  default_admin_username: "admin",
  default_admin_password: "",
};

export function BasicSettingsTab() {
  const { data: config, isLoading } = useSystemConfig();
  const updateConfig = useUpdateSystemConfig();

  const [form, setForm] = useState<BasicFormState>(EMPTY_FORM);
  const [initialized, setInitialized] = useState(false);

  // 首次加载完成后回填表单；后续 refetch 不再覆盖用户未保存的修改
  useEffect(() => {
    if (config && !initialized) {
      setForm({
        http_proxy: config.http_proxy || "",
        https_proxy: config.https_proxy || "",
        no_proxy: config.no_proxy || "",
        service_port_start: config.service_port_start ?? 10000,
        default_admin_username: config.default_admin_username || "admin",
        default_admin_password: config.default_admin_password || "",
      });
      setInitialized(true);
    }
  }, [config, initialized]);

  // 脏检查：与已加载配置一致时禁用保存，避免无意义提交
  const isDirty =
    !config ||
    form.http_proxy !== (config.http_proxy || "") ||
    form.https_proxy !== (config.https_proxy || "") ||
    form.no_proxy !== (config.no_proxy || "") ||
    form.service_port_start !== (config.service_port_start ?? 10000) ||
    form.default_admin_username !== (config.default_admin_username || "admin") ||
    form.default_admin_password !== (config.default_admin_password || "");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateConfig.mutate({
      http_proxy: form.http_proxy || null,
      https_proxy: form.https_proxy || null,
      no_proxy: form.no_proxy || null,
      service_port_start: form.service_port_start,
      default_admin_username: form.default_admin_username.trim() || "admin",
      default_admin_password: form.default_admin_password.trim(),
    });
  };

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">加载配置中...</div>;
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid grid-cols-1 items-start gap-5 xl:grid-cols-2"
    >
      {/* 代理配置 */}
      <Card className="rounded-xl xl:col-span-2">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Network className="h-4 w-4 text-muted-foreground" />
            代理配置
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="http_proxy" className="text-xs font-medium">
                HTTP 代理
              </Label>
              <Input
                id="http_proxy"
                value={form.http_proxy}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, http_proxy: e.target.value }))
                }
                placeholder="http://proxy.example.com:8080"
                className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="https_proxy" className="text-xs font-medium">
                HTTPS 代理
              </Label>
              <Input
                id="https_proxy"
                value={form.https_proxy}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, https_proxy: e.target.value }))
                }
                placeholder="https://proxy.example.com:8080"
                className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
              />
            </div>
            <div className="space-y-1.5 md:col-span-2 xl:col-span-1">
              <Label htmlFor="no_proxy" className="text-xs font-medium">
                No Proxy
              </Label>
              <Input
                id="no_proxy"
                value={form.no_proxy}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, no_proxy: e.target.value }))
                }
                placeholder="localhost,127.0.0.1,.local"
                className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
              />
              <p className="text-xs text-muted-foreground">
                多个地址请使用英文逗号分隔
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 服务端口配置 */}
      <Card className="rounded-xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Plug className="h-4 w-4 text-muted-foreground" />
            服务端口
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-xs space-y-1.5">
            <Label htmlFor="service_port_start" className="text-xs font-medium">
              服务起始端口
            </Label>
            <Input
              id="service_port_start"
              type="number"
              min={1}
              max={65535}
              value={form.service_port_start}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  service_port_start:
                    Number.parseInt(e.target.value, 10) || 10000,
                }))
              }
              className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
            />
            <p className="text-xs text-muted-foreground">
              创建服务时从该端口开始按顺序分配，自动跳过已占用端口。
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 统一服务账号 */}
      <Card className="rounded-xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-muted-foreground" />
            统一服务账号
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label
                htmlFor="default_admin_username"
                className="text-xs font-medium"
              >
                管理员用户名
              </Label>
              <Input
                id="default_admin_username"
                value={form.default_admin_username}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    default_admin_username: e.target.value,
                  }))
                }
                placeholder="admin"
                className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
              />
            </div>
            <div className="space-y-1.5">
              <Label
                htmlFor="default_admin_password"
                className="text-xs font-medium"
              >
                管理员密码
              </Label>
              <PasswordInput
                id="default_admin_password"
                value={form.default_admin_password}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    default_admin_password: e.target.value,
                  }))
                }
                placeholder="留空则每次部署随机生成"
                className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            编排部署时自动配置到各服务（MoviePilot、qBittorrent、Jellyfin），部署完成后自动检测登录是否生效。
          </p>
        </CardContent>
      </Card>

      {/* 保存按钮 */}
      <div className="flex justify-end xl:col-span-2">
        <Button
          type="submit"
          disabled={updateConfig.isPending || !isDirty}
          className="rounded-md"
        >
          {updateConfig.isPending ? "保存中..." : "保存配置"}
        </Button>
      </div>
    </form>
  );
}
