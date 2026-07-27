/**
 * 应用创建/编辑页面
 *
 * 创建模式（/appstore/create）与编辑模式（/appstore/:name/edit）共用，
 * 分区块编辑应用的全部配置：基本信息、部署配置、模板配置、文档。
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { ArrowLeft, Loader2, Trash2 } from "lucide-react";
import {
  useApp,
  useCreateApp,
  useUpdateApp,
  useDeleteApp,
  useUploadAppIcon,
} from "@/hooks/useApps";
import { BasicInfoSection } from "./BasicInfoSection";
import { DeployConfigSection } from "./DeployConfigSection";
import { TemplateSection } from "./TemplateSection";
import { ReadmeSection } from "./ReadmeSection";
import {
  emptyFormState,
  formStateFromApp,
  parseBackupPaths,
  parseTags,
  type AppFormState,
} from "./form-types";

const NAME_PATTERN = /^[a-z0-9][a-z0-9_-]*$/;

export function AppEditPage() {
  const { name } = useParams<{ name?: string }>();
  const isEdit = !!name;
  const navigate = useNavigate();
  const toast = useToast();

  const { data: appDetail, isLoading: isDetailLoading } = useApp(name ?? "", {
    enabled: isEdit,
  });

  const createMutation = useCreateApp();
  const updateMutation = useUpdateApp();
  const deleteMutation = useDeleteApp();
  const uploadIconMutation = useUploadAppIcon();

  const [form, setForm] = useState<AppFormState>(emptyFormState);
  const [initialized, setInitialized] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // 编辑模式：详情加载完成后初始化表单（仅一次）
  useEffect(() => {
    if (isEdit && appDetail && !initialized) {
      setForm(formStateFromApp(appDetail));
      setInitialized(true);
    }
  }, [isEdit, appDetail, initialized]);

  const patchForm = (patch: Partial<AppFormState>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const validationError = useMemo(() => {
    if (!isEdit && !NAME_PATTERN.test(form.name)) {
      return "应用标识只能包含小写字母、数字、中划线和下划线，且以字母或数字开头";
    }
    if (!form.display_name.trim()) return "展示名称不能为空";
    if (!form.yamlTemplate.trim()) return "yaml_template 不能为空";
    try {
      JSON.parse(form.configSchemaText || "{}");
    } catch {
      return "config_schema 不是合法 JSON";
    }
    return null;
  }, [isEdit, form]);

  const handleSave = () => {
    if (validationError) {
      toast.error(validationError);
      return;
    }

    const configSchema = JSON.parse(form.configSchemaText || "{}");
    const payload = {
      display_name: form.display_name.trim(),
      description: form.description.trim() || null,
      category: form.category,
      tags: parseTags(form.tagsText),
      icon: form.icon.trim() || null,
      website: form.website.trim() || null,
      source_url: form.source_url.trim() || null,
      architectures: form.architectures,
      image: form.image.trim() || null,
      default_ports: form.default_ports.map((p) => ({
        port: p.port,
        protocol: p.protocol,
        description: p.description || undefined,
      })),
      config_schema: configSchema,
      yaml_template: form.yamlTemplate,
      readme: form.readme || null,
      version: form.version.trim() || "1.0.0",
      type: form.type,
      changelog: form.changelog || null,
      backup_paths: parseBackupPaths(form.backupPathsText),
    };

    if (isEdit) {
      updateMutation.mutate(
        { name: name!, data: payload },
        { onSuccess: () => navigate("/appstore") }
      );
    } else {
      createMutation.mutate(
        { ...payload, name: form.name.trim() },
        { onSuccess: () => navigate("/appstore") }
      );
    }
  };

  const handleDelete = () => {
    deleteMutation.mutate(name!, {
      onSuccess: () => {
        setDeleteDialogOpen(false);
        navigate("/appstore");
      },
    });
  };

  const handleUploadIcon = (file: File) => {
    uploadIconMutation.mutate(
      { name: name!, file },
      {
        onSuccess: (updated) => {
          patchForm({ icon: updated.icon ?? "" });
        },
      }
    );
  };

  if (isEdit && (isDetailLoading || !initialized)) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        加载应用配置...
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-5xl mx-auto">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/appstore")}
            className="rounded-lg"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            返回
          </Button>
          <h2 className="text-lg font-semibold text-foreground">
            {isEdit ? `编辑应用：${appDetail?.display_name ?? name}` : "创建应用"}
          </h2>
        </div>

        <div className="flex items-center gap-2">
          {isEdit && !appDetail?.is_builtin && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeleteDialogOpen(true)}
              className="rounded-lg text-destructive border-destructive/30 hover:bg-destructive/5 hover:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-1" />
              删除
            </Button>
          )}
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving || !!validationError}
            className="rounded-lg"
          >
            {isSaving && <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />}
            {isEdit ? "保存修改" : "创建应用"}
          </Button>
        </div>
      </div>

      {validationError && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {validationError}
        </div>
      )}

      <BasicInfoSection
        form={form}
        onChange={patchForm}
        isEdit={isEdit}
        onUploadIcon={isEdit ? handleUploadIcon : undefined}
        isUploadingIcon={uploadIconMutation.isPending}
      />

      <DeployConfigSection form={form} onChange={patchForm} />

      <TemplateSection form={form} onChange={patchForm} />

      <ReadmeSection form={form} onChange={patchForm} />

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="删除应用"
        description={`确定要删除应用「${appDetail?.display_name ?? name}」吗？此操作不可恢复。`}
        confirmText="删除"
        destructive
        isPending={deleteMutation.isPending}
        onConfirm={handleDelete}
      />
    </div>
  );
}
