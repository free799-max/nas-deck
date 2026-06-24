/**
 * 基础配置 Tab
 *
 * 包含代理配置与存储配置：
 * - 代理：HTTP/HTTPS/No Proxy
 * - 存储：一行两个目录（宿主机根目录 + Docker 挂载目录）
 */

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { DirectoryPicker } from "@/components/DirectoryPicker";
import {
  useSystemConfig,
  useUpdateSystemConfig,
  useSettingsDirectories,
  useSettingsCreateDirectory,
  useSettingsRenameDirectory,
  useSettingsDeleteDirectory,
  type SystemConfig,
} from "@/hooks/useSettings";
import { Network, HardDrive, FolderOpen } from "lucide-react";

/** 空配置对象 */
const EMPTY_CONFIG: SystemConfig = {
  id: 1,
  http_proxy: "",
  https_proxy: "",
  no_proxy: "",
  storage_host_root_dir: "",
  storage_docker_mount_dir: "",
};

interface DirectoryInputProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  description?: string;
}

/** 目录输入框 + 浏览按钮 */
function DirectoryInput({
  id,
  label,
  value,
  onChange,
  placeholder,
  description,
}: DirectoryInputProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const createDirectory = useSettingsCreateDirectory();
  const renameDirectory = useSettingsRenameDirectory();
  const deleteDirectory = useSettingsDeleteDirectory();

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs font-medium">
        {label}
      </Label>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
        />
        <Button
          type="button"
          variant="secondary"
          size="icon"
          className="h-8 w-8 shrink-0 rounded-md"
          onClick={() => setPickerOpen(true)}
          title="选择目录"
        >
          <FolderOpen className="h-4 w-4" />
        </Button>
        <DirectoryPicker
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          rootPath="/"
          initialPath={value || "/"}
          returnRelative={false}
          onSelect={onChange}
          useDirectoriesQuery={useSettingsDirectories}
          createDirectory={createDirectory}
          renameDirectory={renameDirectory}
          deleteDirectory={deleteDirectory}
        />
      </div>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
    </div>
  );
}

export function BasicSettingsTab() {
  const { data: config, isLoading } = useSystemConfig();
  const updateConfig = useUpdateSystemConfig();

  const [form, setForm] = useState<SystemConfig>(EMPTY_CONFIG);

  // 加载完成后回填表单
  useEffect(() => {
    if (config) {
      setForm({
        ...config,
        http_proxy: config.http_proxy || "",
        https_proxy: config.https_proxy || "",
        no_proxy: config.no_proxy || "",
        storage_host_root_dir: config.storage_host_root_dir || "",
        storage_docker_mount_dir: config.storage_docker_mount_dir || "",
      });
    }
  }, [config]);

  const handleChange = (field: keyof SystemConfig, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateConfig.mutate({
      http_proxy: form.http_proxy || null,
      https_proxy: form.https_proxy || null,
      no_proxy: form.no_proxy || null,
      storage_host_root_dir: form.storage_host_root_dir || null,
      storage_docker_mount_dir: form.storage_docker_mount_dir || null,
    });
  };

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">加载配置中...</div>;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* 代理配置 */}
      <Card className="rounded-xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Network className="h-4 w-4 text-muted-foreground" />
            代理配置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="http_proxy" className="text-xs font-medium">
                HTTP 代理
              </Label>
              <Input
                id="http_proxy"
                value={form.http_proxy}
                onChange={(e) => handleChange("http_proxy", e.target.value)}
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
                onChange={(e) => handleChange("https_proxy", e.target.value)}
                placeholder="https://proxy.example.com:8080"
                className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="no_proxy" className="text-xs font-medium">
              No Proxy
            </Label>
            <Input
              id="no_proxy"
              value={form.no_proxy}
              onChange={(e) => handleChange("no_proxy", e.target.value)}
              placeholder="localhost,127.0.0.1,.local"
              className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
            />
            <p className="text-xs text-muted-foreground">
              多个地址请使用英文逗号分隔
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 存储配置 */}
      <Card className="rounded-xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <HardDrive className="h-4 w-4 text-muted-foreground" />
            存储配置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <DirectoryInput
              id="storage_host_root_dir"
              label="宿主机根目录"
              value={form.storage_host_root_dir}
              onChange={(value) =>
                handleChange("storage_host_root_dir", value)
              }
              placeholder="如 /mnt/data"
              description="将主机根目录挂载到容器的路径，用于部署容器读取目录结构。"
            />
            <div className="space-y-1.5">
              <Label
                htmlFor="storage_docker_mount_dir"
                className="text-xs font-medium"
              >
                Docker 挂载目录
              </Label>
              <Input
                id="storage_docker_mount_dir"
                value={form.storage_docker_mount_dir}
                onChange={(e) =>
                  handleChange("storage_docker_mount_dir", e.target.value)
                }
                placeholder="如 /data"
                className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
              />
              <p className="text-xs text-muted-foreground">
                用于容器部署时容器持久化目录，备份目录。
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 保存按钮 */}
      <div className="flex justify-end">
        <Button
          type="submit"
          disabled={updateConfig.isPending}
          className="rounded-md"
        >
          {updateConfig.isPending ? "保存中..." : "保存配置"}
        </Button>
      </div>
    </form>
  );
}
