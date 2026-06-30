/**
 * 自动化组合部署向导
 *
 * 多步向导：选择应用 -> 共享配置 -> 各应用配置 -> 确认部署。
 */

import { useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { SchemaForm } from "@/components/SchemaForm";
import { useToast } from "@/components/ui/toast";
import { useDeployOrchestration, type AppOrchestration } from "@/hooks/useOrchestrations";
import { useApps } from "@/hooks/useApps";
import { useDeployTasks } from "@/hooks/useDeployTasks";
import { Check, ChevronRight, ChevronLeft } from "lucide-react";

type Step = "select" | "shared" | "apps" | "confirm";

function extractDefaults(schema: Record<string, unknown>): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  const properties = schema?.properties as
    | Record<string, { default?: unknown }>
    | undefined;
  if (properties) {
    for (const [key, prop] of Object.entries(properties)) {
      if (prop && "default" in prop) {
        defaults[key] = prop.default;
      }
    }
  }
  return defaults;
}

interface AutomationDeployWizardProps {
  orchestration: AppOrchestration | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AutomationDeployWizard({
  orchestration,
  open,
  onOpenChange,
}: AutomationDeployWizardProps) {
  const toast = useToast();
  const deployMutation = useDeployOrchestration();
  const { startTask } = useDeployTasks();

  const [step, setStep] = useState<Step>("select");
  const [instanceName, setInstanceName] = useState("");
  const [selectedApps, setSelectedApps] = useState<Set<string>>(new Set());
  const [sharedConfig, setSharedConfig] = useState<Record<string, unknown>>({});
  const [appConfigs, setAppConfigs] = useState<
    Record<string, Record<string, unknown>>
  >({});

  // 重置状态当 orchestration 变化
  useEffect(() => {
    if (!orchestration) {
      setStep("select");
      setInstanceName("");
      setSelectedApps(new Set());
      setSharedConfig({});
      setAppConfigs({});
      return;
    }

    setStep("select");
    setInstanceName(orchestration.display_name || "");
    setSharedConfig(extractDefaults(orchestration.shared_config_schema));

    const initialSelected = new Set<string>();
    const initialAppConfigs: Record<string, Record<string, unknown>> = {};

    for (const item of orchestration.app_composition) {
      if (item.relation === "required" || item.relation === "suggested") {
        initialSelected.add(item.app_name);
      }
      initialAppConfigs[item.app_name] = {};
    }

    setSelectedApps(initialSelected);
    setAppConfigs(initialAppConfigs);
  }, [orchestration]);

  const compositionByName = useMemo(() => {
    if (!orchestration) return {};
    return Object.fromEntries(
      orchestration.app_composition.map((item) => [item.app_name, item])
    );
  }, [orchestration]);

  const selectedAppList = useMemo(
    () => Array.from(selectedApps),
    [selectedApps]
  );

  // 获取所有应用商店应用，用于渲染选中应用的配置表单
  const { data: allApps = [], isLoading: appsLoading } = useApps();
  const appDetailsMap = useMemo(() => {
    return Object.fromEntries(allApps.map((app) => [app.name, app]));
  }, [allApps]);

  if (!orchestration) return null;

  const toggleApp = (appName: string) => {
    const item = compositionByName[appName];
    if (!item || item.relation === "required") return;

    setSelectedApps((prev) => {
      const next = new Set(prev);
      if (next.has(appName)) {
        next.delete(appName);
      } else {
        // 互斥检测：如果新选中的应用与已选中的应用互斥，则取消已选中的
        const conflicts = new Set(item.conflict_with || []);
        for (const selected of next) {
          if (conflicts.has(selected)) {
            next.delete(selected);
          }
        }
        // 同时检查已选中的应用是否把新应用列为互斥
        for (const selected of next) {
          const selectedItem = compositionByName[selected];
          if (selectedItem?.conflict_with?.includes(appName)) {
            next.delete(selected);
          }
        }
        next.add(appName);
      }
      return next;
    });
  };

  const validateStep = (): boolean => {
    if (step === "select") {
      if (!instanceName.trim()) {
        toast.error("请输入实例名称");
        return false;
      }
      // 校验必选应用都已选中
      for (const item of orchestration.app_composition) {
        if (item.relation === "required" && !selectedApps.has(item.app_name)) {
          toast.error(`${item.app_name} 为必选应用`);
          return false;
        }
      }
      return true;
    }
    return true;
  };

  const handleNext = () => {
    if (!validateStep()) return;

    const steps: Step[] = ["select", "shared", "apps", "confirm"];
    const idx = steps.indexOf(step);
    if (idx < steps.length - 1) {
      setStep(steps[idx + 1]);
    }
  };

  const handleBack = () => {
    const steps: Step[] = ["select", "shared", "apps", "confirm"];
    const idx = steps.indexOf(step);
    if (idx > 0) {
      setStep(steps[idx - 1]);
    }
  };

  const handleDeploy = () => {
    if (!instanceName.trim()) {
      toast.error("请输入实例名称");
      return;
    }

    const filteredAppConfigs: Record<string, Record<string, unknown>> = {};
    for (const appName of selectedApps) {
      filteredAppConfigs[appName] = appConfigs[appName] || {};
    }

    deployMutation.mutate(
      {
        name: orchestration.name,
        data: {
          instance_name: instanceName.trim(),
          selected_apps: Array.from(selectedApps),
          app_configs: filteredAppConfigs,
          shared_config: sharedConfig,
        },
      },
      {
        onSuccess: (response) => {
          toast.success("组合部署已启动");
          for (const taskId of response.task_ids) {
            startTask(taskId);
          }
          onOpenChange(false);
        },
      }
    );
  };

  const renderSelectStep = () => (
    <div className="space-y-4">
      <div className="space-y-1">
        <Label htmlFor="instance-name">实例名称</Label>
        <Input
          id="instance-name"
          value={instanceName}
          onChange={(e) => setInstanceName(e.target.value)}
          placeholder="如：我的影视媒体栈"
        />
      </div>

      <div className="space-y-2">
        <Label>选择要部署的应用</Label>
        <div className="space-y-2">
          {orchestration.app_composition.map((item) => {
            const selected = selectedApps.has(item.app_name);
            const disabled = item.relation === "required";
            return (
              <div
                key={item.app_name}
                className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                  selected
                    ? "border-primary bg-primary/5"
                    : "border-border bg-white hover:bg-muted/30"
                } ${disabled ? "opacity-80" : "cursor-pointer"}`}
                onClick={() => toggleApp(item.app_name)}
              >
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={selected}
                    disabled={disabled}
                    readOnly
                    className="h-4 w-4 rounded border-input"
                  />
                  <div>
                    <div className="text-sm font-medium">{item.app_name}</div>
                    {item.group && (
                      <div className="text-xs text-muted-foreground">
                        分组：{item.group}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      item.relation === "required"
                        ? "default"
                        : item.relation === "suggested"
                        ? "secondary"
                        : "outline"
                    }
                    className="text-xs"
                  >
                    {item.relation === "required"
                      ? "必选"
                      : item.relation === "suggested"
                      ? "推荐"
                      : item.relation === "conflicting"
                      ? "互斥"
                      : "可选"}
                  </Badge>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );

  const renderSharedStep = () => (
    <div className="space-y-4">
      <div className="text-sm text-muted-foreground">
        以下配置会共享给所有选中的应用，可在各应用配置中覆盖
      </div>
      <SchemaForm
        schema={orchestration.shared_config_schema as never}
        data={sharedConfig}
        onChange={setSharedConfig}
      />
    </div>
  );

  const renderAppsStep = () => (
    <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
      {appsLoading ? (
        <div className="text-sm text-muted-foreground py-4">加载应用配置中...</div>
      ) : (
        selectedAppList.map((appName) => {
          const app = appDetailsMap[appName];
          if (!app) {
            return (
              <div key={appName} className="text-sm text-muted-foreground py-4">
                未找到应用 {appName}
              </div>
            );
          }

          return (
            <div key={appName} className="rounded-xl border bg-card p-4 shadow-sm">
              <h4 className="text-sm font-semibold mb-3">{app.display_name}</h4>
              <SchemaForm
                schema={app.config_schema as never}
                data={appConfigs[appName] || {}}
                onChange={(data) =>
                  setAppConfigs((prev) => ({ ...prev, [appName]: data }))
                }
                instanceName={`${instanceName}-${appName}`}
                image={app.image || undefined}
              />
            </div>
          );
        })
      )}
    </div>
  );

  const renderConfirmStep = () => (
    <div className="space-y-4">
      <div className="rounded-lg bg-muted/50 p-4 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">实例名称</span>
          <span className="font-medium">{instanceName}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">部署应用数</span>
          <span className="font-medium">{selectedApps.size} 个</span>
        </div>
        <div className="pt-2">
          <div className="text-sm text-muted-foreground mb-1.5">应用列表</div>
          <div className="flex flex-wrap gap-1.5">
            {Array.from(selectedApps).map((appName) => (
              <Badge key={appName} variant="secondary" className="text-xs">
                {appName}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const stepTitles: Record<Step, string> = {
    select: "选择应用",
    shared: "共享配置",
    apps: "应用配置",
    confirm: "确认部署",
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle>部署 {orchestration.display_name}</DialogTitle>
          <DialogDescription>
            {orchestration.description || "选择应用并填写配置后一键部署"}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 py-2 flex-shrink-0">
          {(["select", "shared", "apps", "confirm"] as Step[]).map(
            (s, index) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`flex items-center justify-center h-6 w-6 rounded-full text-xs font-medium ${
                    step === s
                      ? "bg-primary text-primary-foreground"
                      : index < ["select", "shared", "apps", "confirm"].indexOf(step)
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {index < ["select", "shared", "apps", "confirm"].indexOf(step) ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    index + 1
                  )}
                </div>
                <span
                  className={`text-xs ${
                    step === s ? "text-primary font-medium" : "text-muted-foreground"
                  }`}
                >
                  {stepTitles[s]}
                </span>
                {index < 3 && (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </div>
            )
          )}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 py-2">
          {step === "select" && renderSelectStep()}
          {step === "shared" && renderSharedStep()}
          {step === "apps" && renderAppsStep()}
          {step === "confirm" && renderConfirmStep()}
        </div>

        <div className="flex justify-between gap-2 mt-4 flex-shrink-0">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={deployMutation.isPending}
          >
            取消
          </Button>
          <div className="flex gap-2">
            {step !== "select" && (
              <Button variant="outline" onClick={handleBack}>
                <ChevronLeft className="h-4 w-4 mr-1" />
                上一步
              </Button>
            )}
            {step !== "confirm" ? (
              <Button onClick={handleNext}>
                下一步
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            ) : (
              <Button
                onClick={handleDeploy}
                disabled={deployMutation.isPending}
              >
                {deployMutation.isPending ? "部署中..." : "确认部署"}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
