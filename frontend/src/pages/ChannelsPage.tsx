/**
 * 通知渠道管理页面组件
 *
 * 管理通知渠道的完整生命周期，包括：
 * - 查看所有已配置的通知渠道（卡片列表）
 * - 通过内联表单添加新的通知渠道（选择渠道类型、填写配置参数）
 * - 发送测试通知验证渠道配置是否正确
 * - 删除已有通知渠道
 *
 * 表单中的配置字段根据所选渠道类型的 config_schema 动态生成。
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Trash2, Plus, Send } from "lucide-react";
import {
  useNotifiers,
  useChannels,
  useCreateChannel,
  useDeleteChannel,
  useTestNotifier,
} from "@/hooks/useNotifications";

/**
 * 通知渠道管理页面组件
 *
 * 提供通知渠道的增删查功能：
 * 1. 展示已配置的通知渠道卡片列表（类型、启用状态、删除按钮）
 * 2. 内联表单添加新渠道（选择类型 -> 填写动态配置字段 -> 创建/测试）
 * 3. 测试通知功能，向所选渠道发送测试消息
 * 4. 删除已有渠道
 */
export function ChannelsPage() {
  // 获取所有可用的通知器类型（如 Telegram、Email 等）
  const { data: notifiers = [] } = useNotifiers();
  // 获取所有已配置的通知渠道
  const { data: channels = [] } = useChannels();
  // 创建通知渠道的 mutation
  const createChannel = useCreateChannel();
  // 删除通知渠道的 mutation
  const deleteChannel = useDeleteChannel();
  // 发送测试通知的 mutation
  const testNotifier = useTestNotifier();

  // 当前选中的通知渠道类型
  const [selectedType, setSelectedType] = useState<string | null>(null);
  // 动态表单配置数据，键为配置字段名，值为输入值
  const [formData, setFormData] = useState<Record<string, string>>({});
  // 控制添加渠道表单的显示/隐藏
  const [showForm, setShowForm] = useState(false);

  // 从可用通知器列表中查找当前选中的通知器信息
  const selectedNotifier = notifiers.find((n) => n.name === selectedType);
  // 从选中通知器的 config_schema 中提取配置字段属性，用于动态渲染表单
  const configProperties =
    (selectedNotifier?.config_schema as { properties?: Record<string, { title?: string }> })
      ?.properties ?? {};

  /**
   * 处理创建通知渠道
   *
   * 验证必填字段（selectedType）后，调用 createChannel mutation 创建新渠道。
   * 创建成功后隐藏表单并重置所有表单状态。
   */
  const handleCreate = () => {
    // 必须选择渠道类型
    if (!selectedType) return;
    createChannel.mutate(
      { type: selectedType, config: formData, enabled: true },
      {
        onSuccess: () => {
          // 创建成功后隐藏表单并重置状态
          setShowForm(false);
          setSelectedType(null);
          setFormData({});
        },
      }
    );
  };

  /**
   * 处理发送测试通知
   *
   * 使用当前选中的渠道类型和填写的配置参数，发送一条测试通知消息，
   * 用于验证渠道配置是否正确。
   */
  const handleTest = () => {
    // 必须选择渠道类型
    if (!selectedType) return;
    testNotifier.mutate({ type: selectedType, config: formData });
  };

  return (
    <div>
      {/* 页面头部：标题 + 添加渠道按钮 */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">通知渠道</h2>
        {/* 切换添加渠道表单的显示状态 */}
        <Button onClick={() => setShowForm(!showForm)}>
          <Plus className="h-4 w-4 mr-2" />
          添加渠道
        </Button>
      </div>

      {/* 添加渠道的内联表单，仅在 showForm 为 true 时显示 */}
      {showForm && (
        <Card className="rounded-xl mb-6">
          <CardHeader>
            <CardTitle className="text-base">添加通知渠道</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* 渠道类型选择区域，以可点击的徽章形式展示 */}
            <div className="space-y-2">
              <Label>渠道类型</Label>
              <div className="flex gap-2 flex-wrap">
                {/* 遍历可用通知器，渲染为可点击的徽章 */}
                {notifiers.map((n) => (
                  <Badge
                    key={n.name}
                    variant={selectedType === n.name ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => {
                      // 选中该渠道类型并重置配置表单
                      setSelectedType(n.name);
                      setFormData({});
                    }}
                  >
                    {n.name}
                  </Badge>
                ))}
              </div>
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
            {/* 操作按钮组：创建 + 测试 */}
            <div className="flex gap-2">
              {/* 创建按钮，需选择渠道类型且不在提交中状态 */}
              <Button
                onClick={handleCreate}
                disabled={!selectedType || createChannel.isPending}
              >
                {createChannel.isPending ? "创建中..." : "创建"}
              </Button>
              {/* 测试按钮，发送测试通知验证配置 */}
              <Button variant="outline" onClick={handleTest} disabled={!selectedType}>
                <Send className="h-4 w-4 mr-2" />
                测试
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 已配置的通知渠道卡片网格，响应式布局 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 遍历通知渠道，渲染每个渠道卡片 */}
        {channels.map((ch) => (
          <Card key={ch.id} className="rounded-xl">
            {/* 卡片头部：渠道类型名称（首字母大写） + 删除按钮 */}
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base capitalize">{ch.type}</CardTitle>
              {/* 删除按钮，点击后删除该通知渠道 */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => deleteChannel.mutate(ch.id)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </CardHeader>
            <CardContent>
              {/* 启用/禁用状态徽章 */}
              <Badge variant={ch.enabled ? "default" : "outline"}>
                {ch.enabled ? "启用" : "禁用"}
              </Badge>
            </CardContent>
          </Card>
        ))}
        {/* 渠道列表为空且表单未显示时的引导提示 */}
        {channels.length === 0 && !showForm && (
          <p className="text-muted-foreground col-span-full text-center py-12">
            暂无通知渠道，点击"添加渠道"开始配置。
          </p>
        )}
      </div>
    </div>
  );
}
