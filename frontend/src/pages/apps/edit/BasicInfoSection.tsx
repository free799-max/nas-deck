/**
 * 应用编辑页 - 基本信息区块
 *
 * 名称、展示名、描述、分类、标签、图标、链接、架构、版本、类型。
 */

import { useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Upload } from "lucide-react";
import { AppIcon } from "../AppIcon";
import {
  ARCH_OPTIONS,
  CATEGORY_OPTIONS,
  type AppFormState,
} from "./form-types";

interface BasicInfoSectionProps {
  form: AppFormState;
  onChange: (patch: Partial<AppFormState>) => void;
  /** 编辑模式下禁用 name 字段 */
  isEdit: boolean;
  /** 上传图标（仅编辑模式可用，应用需已存在） */
  onUploadIcon?: (file: File) => void;
  isUploadingIcon?: boolean;
}

export function BasicInfoSection({
  form,
  onChange,
  isEdit,
  onUploadIcon,
  isUploadingIcon,
}: BasicInfoSectionProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleArch = (arch: string) => {
    const next = form.architectures.includes(arch)
      ? form.architectures.filter((a) => a !== arch)
      : [...form.architectures, arch];
    onChange({ architectures: next });
  };

  return (
    <Card className="rounded-xl">
      <CardContent className="p-5 space-y-4">
        <h3 className="text-sm font-semibold text-foreground">基本信息</h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="app-name">应用标识 *</Label>
            <Input
              id="app-name"
              value={form.name}
              onChange={(e) => onChange({ name: e.target.value })}
              placeholder="如 moviepilot（小写字母/数字/中划线）"
              disabled={isEdit}
            />
            {isEdit && (
              <p className="text-xs text-muted-foreground">
                应用标识创建后不可修改
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="app-display-name">展示名称 *</Label>
            <Input
              id="app-display-name"
              value={form.display_name}
              onChange={(e) => onChange({ display_name: e.target.value })}
              placeholder="如 MoviePilot"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="app-description">描述</Label>
          <textarea
            id="app-description"
            value={form.description}
            onChange={(e) => onChange({ description: e.target.value })}
            placeholder="应用简介"
            rows={2}
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="app-category">分类</Label>
            <select
              id="app-category"
              value={form.category}
              onChange={(e) => onChange({ category: e.target.value })}
              className="h-9 w-full rounded-lg border border-border bg-white px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="app-version">版本</Label>
            <Input
              id="app-version"
              value={form.version}
              onChange={(e) => onChange({ version: e.target.value })}
              placeholder="1.0.0"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="app-type">类型</Label>
            <select
              id="app-type"
              value={form.type}
              onChange={(e) => onChange({ type: e.target.value })}
              className="h-9 w-full rounded-lg border border-border bg-white px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="compose">Compose</option>
              <option value="container">Container</option>
            </select>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="app-tags">标签</Label>
          <Input
            id="app-tags"
            value={form.tagsText}
            onChange={(e) => onChange({ tagsText: e.target.value })}
            placeholder="多个标签用逗号分隔，如：media, automation"
          />
        </div>

        <div className="space-y-1.5">
          <Label>支持架构</Label>
          <div className="flex items-center gap-4">
            {ARCH_OPTIONS.map((arch) => (
              <label
                key={arch}
                className="flex items-center gap-1.5 text-sm text-foreground cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={form.architectures.includes(arch)}
                  onChange={() => toggleArch(arch)}
                  className="h-4 w-4 rounded border-border accent-primary"
                />
                {arch}
              </label>
            ))}
          </div>
        </div>

        {/* 图标 */}
        <div className="space-y-1.5">
          <Label htmlFor="app-icon">图标</Label>
          <div className="flex items-center gap-3">
            <AppIcon
              app={{
                name: form.name || "placeholder",
                icon: form.icon || null,
              }}
              className="h-12 w-12 rounded-lg border border-border/60 shrink-0"
            />
            <div className="flex-1 space-y-2">
              <Input
                id="app-icon"
                value={form.icon}
                onChange={(e) => onChange({ icon: e.target.value })}
                placeholder="https:// 外链，或留空回退本地 /icons/apps/<name>.svg"
              />
              {isEdit && onUploadIcon && (
                <div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".svg,.png,.jpg,.jpeg,.webp"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) onUploadIcon(file);
                      e.target.value = "";
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isUploadingIcon}
                    onClick={() => fileInputRef.current?.click()}
                    className="rounded-lg"
                  >
                    <Upload className="h-3.5 w-3.5 mr-1.5" />
                    {isUploadingIcon ? "上传中..." : "上传图标文件"}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="app-website">官网</Label>
            <Input
              id="app-website"
              value={form.website}
              onChange={(e) => onChange({ website: e.target.value })}
              placeholder="https://"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="app-source-url">源码仓库</Label>
            <Input
              id="app-source-url"
              value={form.source_url}
              onChange={(e) => onChange({ source_url: e.target.value })}
              placeholder="https://github.com/..."
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
