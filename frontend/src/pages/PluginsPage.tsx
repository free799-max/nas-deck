/**
 * 插件管理页面组件
 *
 * 展示所有插件实例的卡片列表，每张卡片显示插件显示名称、插件类型和启用状态。
 * 支持通过 Dialog 弹窗表单添加新的插件实例，表单包含：
 * - 插件选择（从可用插件列表中选择）
 * - 自定义显示名称
 * - 根据插件配置 schema 动态生成的配置字段
 *
 * 同时支持删除已有的插件实例。
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
import {
  useAvailablePlugins,
  usePluginInstances,
  useCreateInstance,
  useDeleteInstance,
} from "@/hooks/usePlugins";

/**
 * 插件管理页面组件
 *
 * 管理插件实例的完整生命周期：
 * 1. 查看所有已创建的插件实例（卡片网格）
 * 2. 通过 Dialog 弹窗添加新实例（选择插件类型、填写名称和配置）
 * 3. 删除已有实例
 *
 * 表单中的配置字段根据所选插件的 config_schema 动态生成。
 */
export function PluginsPage() {
  // 获取所有可用插件（支持创建实例的插件列表）
  const { data: available = [] } = useAvailablePlugins();
  // 获取所有已创建的插件实例
  const { data: instances = [] } = usePluginInstances();
  // 创建插件实例的 mutation
  const createInstance = useCreateInstance();
  // 删除插件实例的 mutation
  const deleteInstance = useDeleteInstance();
  // 控制"添加实例"弹窗的显示/隐藏
  const [open, setOpen] = useState(false);
  // 当前选中的插件名称
  const [selectedPlugin, setSelectedPlugin] = useState<string | null>(null);
  // 动态表单配置数据，键为配置字段名，值为输入值
  const [formData, setFormData] = useState<Record<string, string>>({});
  // 用户自定义的插件实例显示名称
  const [displayName, setDisplayName] = useState("");

  /**
   * 处理创建插件实例
   *
   * 验证必填字段（selectedPlugin 和 displayName）后，
   * 调用 createInstance mutation 创建新实例。
   * 创建成功后关闭弹窗并重置表单状态。
   */
  const handleCreate = () => {
    // 必须选择插件且填写显示名称
    if (!selectedPlugin || !displayName) return;
    createInstance.mutate(
      {
        plugin_name: selectedPlugin,
        display_name: displayName,
        config: formData,
      },
      {
        onSuccess: () => {
          // 创建成功后关闭弹窗并重置所有表单状态
          setOpen(false);
          setSelectedPlugin(null);
          setFormData({});
          setDisplayName("");
        },
      }
    );
  };

  // 从可用插件列表中查找当前选中的插件信息，用于获取配置 schema
  const selectedPluginInfo = available.find((p) => p.name === selectedPlugin);
  // 从选中插件的 config_schema 中提取配置字段属性，用于动态渲染表单
  const configProperties =
    (selectedPluginInfo?.config_schema as { properties?: Record<string, { title?: string }> })
      ?.properties ?? {};

  return (
    <div>
      {/* 页面头部：标题 + 添加实例按钮 */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">插件管理</h2>
        {/* 添加插件实例的弹窗 */}
        <Dialog open={open} onOpenChange={setOpen}>
          {/* 弹窗触发按钮 */}
          <DialogTrigger
            render={
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                添加实例
              </Button>
            }
          />
          {/* 弹窗内容 */}
          <DialogContent>
            <DialogHeader>
              <DialogTitle>添加插件实例</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {/* 插件选择区域，以可点击的徽章形式展示可用插件 */}
              <div className="space-y-2">
                <Label>选择插件</Label>
                <div className="flex gap-2 flex-wrap">
                  {/* 遍历可用插件，渲染为可点击的徽章 */}
                  {available.map((p) => (
                    <Badge
                      key={p.name}
                      variant={selectedPlugin === p.name ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => {
                        // 选中该插件并重置配置表单
                        setSelectedPlugin(p.name);
                        setFormData({});
                      }}
                    >
                      {p.display_name}
                    </Badge>
                  ))}
                </div>
              </div>
              {/* 显示名称输入框 */}
              <div className="space-y-2">
                <Label>显示名称</Label>
                <Input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="My Jellyfin"
                />
              </div>
              {/* 根据 config_schema 动态生成的配置字段 */}
              {Object.entries(configProperties).map(([key, schema]) => (
                <div key={key} className="space-y-1">
                  {/* 字段标签，优先使用 schema 中的 title，否则使用字段名 */}
                  <Label>{schema.title ?? key}</Label>
                  <Input
                    value={formData[key] ?? ""}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                </div>
              ))}
              {/* 创建按钮，需满足必填条件且不在提交中状态 */}
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
      </div>

      {/* 插件实例卡片网格，响应式布局 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 遍历插件实例，渲染每个实例卡片 */}
        {instances.map((inst) => (
          <Card key={inst.id} className="rounded-xl">
            {/* 卡片头部：显示名称 + 删除按钮 */}
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">{inst.display_name}</CardTitle>
              {/* 删除按钮，点击后删除该插件实例 */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => deleteInstance.mutate(inst.id)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </CardHeader>
            <CardContent>
              {/* 插件类型徽章 */}
              <Badge variant="secondary">{inst.plugin_name}</Badge>
              {/* 启用/禁用状态徽章 */}
              <Badge
                variant={inst.enabled ? "default" : "outline"}
                className="ml-2"
              >
                {inst.enabled ? "Active" : "Disabled"}
              </Badge>
            </CardContent>
          </Card>
        ))}
        {/* 实例列表为空时的引导提示 */}
        {instances.length === 0 && (
          <p className="text-muted-foreground col-span-full text-center py-12">
            暂无插件实例，点击"添加实例"开始配置。
          </p>
        )}
      </div>
    </div>
  );
}
