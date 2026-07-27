/**
 * 应用编辑页 - 模板配置区块
 *
 * config_schema 支持可视化编辑（字段/端口/挂载/环境变量等结构化表单）
 * 与源码编辑（JSON）两种模式；yaml_template 可根据 config_schema 一键生成，
 * 也可手动编写 Jinja2 YAML，支持调用后端接口实时预览渲染结果。
 */

import { useMemo, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import { yaml } from "@codemirror/lang-yaml";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { Eye, Loader2, Wand2 } from "lucide-react";
import { useAppTemplatePreview } from "@/hooks/useApps";
import type { AppFormState } from "./form-types";
import { SchemaBuilder } from "./SchemaBuilder";
import {
  builderModelToSchema,
  generateYamlTemplate,
  schemaToBuilderModel,
} from "./schema-builder";

interface TemplateSectionProps {
  form: AppFormState;
  onChange: (patch: Partial<AppFormState>) => void;
}

export function TemplateSection({ form, onChange }: TemplateSectionProps) {
  const previewMutation = useAppTemplatePreview();
  const toast = useToast();
  const [editorMode, setEditorMode] = useState<"visual" | "source">("visual");
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [previewResult, setPreviewResult] = useState<{
    yaml: string | null;
    error: string | null;
  } | null>(null);

  // config_schema 解析结果与可视化模型（不支持的结构回退源码编辑）
  const parsedSchema = useMemo(() => {
    try {
      return JSON.parse(form.configSchemaText || "{}");
    } catch {
      return null;
    }
  }, [form.configSchemaText]);

  const builderModel = useMemo(
    () => (parsedSchema ? schemaToBuilderModel(parsedSchema) : null),
    [parsedSchema]
  );

  const visualActive = editorMode === "visual" && builderModel !== null;

  const switchToVisual = () => {
    if (!parsedSchema) {
      toast.error("config_schema 不是合法 JSON，无法切换为可视化编辑");
      return;
    }
    if (!builderModel) {
      toast.error("当前 config_schema 包含不支持的字段结构，仅支持源码编辑");
      return;
    }
    setEditorMode("visual");
  };

  const handlePreview = () => {
    if (!parsedSchema) {
      setPreviewResult({ yaml: null, error: "config_schema 不是合法 JSON" });
      return;
    }

    previewMutation.mutate(
      {
        yaml_template: form.yamlTemplate,
        config_schema: parsedSchema,
        image: form.image || null,
        app_name: form.name || "preview-app",
      },
      { onSuccess: (result) => setPreviewResult(result) }
    );
  };

  const doGenerateYaml = () => {
    if (!parsedSchema) {
      toast.error("config_schema 不是合法 JSON，无法生成模板");
      return;
    }
    const yamlTemplate = generateYamlTemplate(parsedSchema, {
      appName: form.name || "app",
      hasImage: !!form.image.trim(),
    });
    onChange({ yamlTemplate });
    setGenerateDialogOpen(false);
    toast.success("已根据配置生成 YAML 模板，可按需手动调整");
  };

  const handleGenerateClick = () => {
    if (!parsedSchema) {
      toast.error("config_schema 不是合法 JSON，无法生成模板");
      return;
    }
    if (form.yamlTemplate.trim()) {
      setGenerateDialogOpen(true);
    } else {
      doGenerateYaml();
    }
  };

  return (
    <Card className="rounded-xl">
      <CardContent className="p-5 space-y-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">模板配置</h3>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handlePreview}
            disabled={previewMutation.isPending || !form.yamlTemplate.trim()}
            className="rounded-lg"
          >
            {previewMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Eye className="h-3.5 w-3.5 mr-1.5" />
            )}
            预览渲染
          </Button>
        </div>

        {/* config_schema */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label>config_schema（部署向导表单配置）</Label>
            <div className="flex items-center rounded-lg border overflow-hidden">
              <button
                type="button"
                onClick={switchToVisual}
                className={`px-2.5 h-7 text-xs transition-colors ${
                  visualActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent"
                }`}
              >
                可视化
              </button>
              <button
                type="button"
                onClick={() => setEditorMode("source")}
                className={`px-2.5 h-7 text-xs transition-colors ${
                  !visualActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent"
                }`}
              >
                源码
              </button>
            </div>
          </div>

          {visualActive ? (
            <SchemaBuilder
              model={builderModel}
              onChange={(model) =>
                onChange({
                  configSchemaText: JSON.stringify(
                    builderModelToSchema(model),
                    null,
                    2
                  ),
                })
              }
            />
          ) : (
            <>
              {editorMode === "visual" && builderModel === null && (
                <p className="text-xs text-muted-foreground">
                  当前 config_schema 包含不支持的字段结构，已回退为源码编辑
                </p>
              )}
              <div className="border rounded-md overflow-hidden">
                <CodeMirror
                  value={form.configSchemaText}
                  height="280px"
                  extensions={[json()]}
                  onChange={(value) => onChange({ configSchemaText: value })}
                  className="text-sm"
                  basicSetup={{
                    lineNumbers: true,
                    highlightActiveLineGutter: true,
                    highlightActiveLine: true,
                    foldGutter: false,
                  }}
                />
              </div>
            </>
          )}
        </div>

        {/* yaml_template */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label>yaml_template（Jinja2 Compose YAML 模板）*</Label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleGenerateClick}
              className="rounded-lg h-7 text-xs"
            >
              <Wand2 className="h-3.5 w-3.5 mr-1" />
              根据配置生成
            </Button>
          </div>
          <div className="border rounded-md overflow-hidden">
            <CodeMirror
              value={form.yamlTemplate}
              height="320px"
              extensions={[yaml()]}
              onChange={(value) => onChange({ yamlTemplate: value })}
              className="text-sm"
              basicSetup={{
                lineNumbers: true,
                highlightActiveLineGutter: true,
                highlightActiveLine: true,
                foldGutter: false,
              }}
            />
          </div>
        </div>

        {/* 预览结果 */}
        {previewResult && (
          <div className="space-y-1.5">
            <Label>预览结果</Label>
            {previewResult.error ? (
              <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive whitespace-pre-wrap">
                {previewResult.error}
              </div>
            ) : (
              <div className="border rounded-md overflow-hidden">
                <CodeMirror
                  value={previewResult.yaml ?? ""}
                  height="240px"
                  extensions={[yaml()]}
                  editable={false}
                  className="text-sm"
                  basicSetup={{
                    lineNumbers: true,
                    highlightActiveLineGutter: false,
                    highlightActiveLine: false,
                    foldGutter: false,
                  }}
                />
              </div>
            )}
          </div>
        )}

        <ConfirmDialog
          open={generateDialogOpen}
          onOpenChange={setGenerateDialogOpen}
          title="生成 YAML 模板"
          description="将根据当前 config_schema 生成新的 YAML 模板（端口、挂载目录、环境变量、设备映射自动接线），并覆盖当前内容。确定继续吗？"
          confirmText="生成并覆盖"
          onConfirm={doGenerateYaml}
        />
      </CardContent>
    </Card>
  );
}
