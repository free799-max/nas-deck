/**
 * 编排部署弹窗
 */

import { useState } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SchemaForm } from "@/components/SchemaForm";
import { useToast } from "@/components/ui/toast";
import type { AppOrchestration } from "@/hooks/useOrchestrations";
import type { SchemaProperty } from "@/components/SchemaForm";

function extractDefaults(schema: Record<string, unknown>): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  const properties = schema?.properties as
    | Record<string, { default?: unknown }>
    | undefined;
  const required = new Set((schema?.required as string[] | undefined) || []);
  if (properties) {
    for (const [key, prop] of Object.entries(properties)) {
      if (prop && "default" in prop) {
        defaults[key] = prop.default;
      } else if (required.has(key)) {
        // 必填项若无默认值，先用空字符串占位，避免 schema 校验立即失败
        defaults[key] = "";
      }
    }
  }
  return defaults;
}

interface OrchestrationDeployDialogProps {
  orchestration: AppOrchestration | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeploy: (data: {
    instance_name: string;
    config: Record<string, unknown>;
  }) => void;
  isDeploying?: boolean;
}

export function OrchestrationDeployDialog({
  orchestration,
  open,
  onOpenChange,
  onDeploy,
  isDeploying = false,
}: OrchestrationDeployDialogProps) {
  const [instanceName, setInstanceName] = useState(
    orchestration?.display_name ?? ""
  );
  const [config, setConfig] = useState<Record<string, unknown>>(
    () => (orchestration ? extractDefaults(orchestration.config_schema) : {})
  );
  const toast = useToast();

  if (!orchestration) return null;

  const handleDeploy = () => {
    if (!instanceName.trim()) {
      toast.error("请输入实例名称");
      return;
    }
    onDeploy({ instance_name: instanceName.trim(), config });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle>部署 {orchestration.display_name}</DialogTitle>
          <DialogDescription>
            {orchestration.description || "填写配置后一键部署"}
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="config" className="flex-1 overflow-hidden flex flex-col min-h-0">
          <TabsList className="grid w-full grid-cols-2 flex-shrink-0">
            <TabsTrigger value="config">配置</TabsTrigger>
            <TabsTrigger value="readme">说明</TabsTrigger>
          </TabsList>

          <TabsContent value="config" className="flex-1 overflow-y-auto space-y-4 pr-1 min-h-0">
            <div className="space-y-1">
              <Label htmlFor="instance-name">实例名称</Label>
              <Input
                id="instance-name"
                value={instanceName}
                onChange={(e) => setInstanceName(e.target.value)}
                placeholder="如：我的 Jellyfin 媒体栈"
              />
            </div>

            <SchemaForm
              schema={
                orchestration.config_schema as {
                  properties?: Record<string, SchemaProperty>;
                }
              }
              data={config}
              onChange={setConfig}
            />
          </TabsContent>

          <TabsContent value="readme" className="flex-1 overflow-y-auto min-h-0">
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <pre className="whitespace-pre-wrap font-sans text-sm text-foreground bg-muted p-4 rounded-lg">
                {(orchestration as unknown as { readme?: string }).readme || "暂无说明"}
              </pre>
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-end gap-2 mt-4 flex-shrink-0">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isDeploying}
          >
            取消
          </Button>
          <Button onClick={handleDeploy} disabled={isDeploying}>
            {isDeploying ? "部署中..." : "一键部署"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
