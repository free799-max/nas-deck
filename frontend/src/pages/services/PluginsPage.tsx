/**
 * 服务编排页面组件
 *
 * 管理插件实例。
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Plus, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import {
  useAvailablePlugins,
  usePluginInstances,
  useCreateInstance,
  useDeleteInstance,
} from "@/hooks/usePlugins";

/**
 * 插件实例标签页
 */
function PluginInstancesTab() {
  const { data: available = [] } = useAvailablePlugins();
  const { data: instances = [] } = usePluginInstances();
  const createInstance = useCreateInstance();
  const deleteInstance = useDeleteInstance();
  const [open, setOpen] = useState(false);
  const [selectedPlugin, setSelectedPlugin] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [displayName, setDisplayName] = useState("");

  const handleCreate = () => {
    if (!selectedPlugin || !displayName) return;
    createInstance.mutate(
      {
        plugin_name: selectedPlugin,
        display_name: displayName,
        config: formData,
      },
      {
        onSuccess: () => {
          setOpen(false);
          setSelectedPlugin(null);
          setFormData({});
          setDisplayName("");
        },
      }
    );
  };

  const selectedPluginInfo = available.find((p) => p.name === selectedPlugin);
  const configProperties =
    (
      selectedPluginInfo?.config_schema as {
        properties?: Record<string, { title?: string }>;
      }
    )?.properties ?? {};

  return (
    <div>
      <PageHeader title="插件实例" description="管理所有插件实例及其配置">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                添加实例
              </Button>
            }
          />
          <DialogContent>
            <DialogHeader>
              <DialogTitle>添加插件实例</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>选择插件</Label>
                <div className="flex gap-2 flex-wrap">
                  {available.map((p) => (
                    <Badge
                      key={p.name}
                      variant={selectedPlugin === p.name ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => {
                        setSelectedPlugin(p.name);
                        setFormData({});
                      }}
                    >
                      {p.display_name}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label>显示名称</Label>
                <Input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="My Jellyfin"
                />
              </div>
              {Object.entries(configProperties).map(([key, schema]) => (
                <div key={key} className="space-y-1">
                  <Label>{schema.title ?? key}</Label>
                  <Input
                    value={formData[key] ?? ""}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                </div>
              ))}
              <Button
                onClick={handleCreate}
                className="w-full"
                disabled={!selectedPlugin || !displayName || createInstance.isPending}
              >
                {createInstance.isPending ? "创建中..." : "创建"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {instances.map((inst) => (
          <Card key={inst.id} className="rounded-xl">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">{inst.display_name}</CardTitle>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => deleteInstance.mutate(inst.id)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </CardHeader>
            <CardContent>
              <Badge variant="secondary">{inst.plugin_name}</Badge>
              <Badge
                variant={inst.enabled ? "default" : "outline"}
                className="ml-2"
              >
                {inst.enabled ? "Active" : "Disabled"}
              </Badge>
            </CardContent>
          </Card>
        ))}
        {instances.length === 0 && (
          <p className="text-muted-foreground col-span-full text-center py-12">
            暂无插件实例，点击"添加实例"开始配置。
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * 服务编排页面
 */
export function PluginsPage() {
  return (
    <div className="space-y-6">
      <PluginInstancesTab />
    </div>
  );
}
