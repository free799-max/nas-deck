/**
 * 订阅管理页面组件
 *
 * 展示所有订阅的卡片列表，每张卡片显示订阅标题、状态徽章和最后检查时间。
 * 支持通过删除按钮移除单个订阅。
 * 当列表为空时显示引导提示信息。
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Trash2 } from "lucide-react";
import { useSubscriptions, useDeleteSubscription } from "@/hooks/useSubscriptions";

/**
 * 订阅管理页面组件
 *
 * 获取订阅列表数据并提供删除功能。
 * 使用响应式网格布局展示订阅卡片，每张卡片包含
 * 订阅标题、状态标签、最后检查时间以及删除按钮。
 */
export function SubscriptionsPage() {
  // 获取所有订阅数据，默认为空数组
  const { data: subscriptions = [] } = useSubscriptions();
  // 获取删除订阅的 mutation 操作
  const deleteSub = useDeleteSubscription();

  return (
    <div>
      {/* 页面标题 */}
      <h2 className="text-2xl font-bold mb-6">订阅管理</h2>
      {/* 订阅卡片网格，响应式布局：1列(小屏) -> 2列(中屏) -> 3列(大屏) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 遍历订阅列表，渲染每个订阅卡片 */}
        {subscriptions.map((sub) => (
          <Card key={sub.id} className="rounded-xl">
            {/* 卡片头部：订阅标题 + 删除按钮 */}
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">{sub.item_title}</CardTitle>
              {/* 删除按钮，点击后调用删除接口 */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => deleteSub.mutate(sub.id)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </CardHeader>
            <CardContent>
              {/* 状态徽章：活跃状态用默认样式，其他状态用次要样式 */}
              <Badge variant={sub.status === "active" ? "default" : "secondary"}>
                {sub.status}
              </Badge>
              {/* 最后检查时间，仅在存在时显示 */}
              {sub.last_checked && (
                <span className="text-xs text-muted-foreground ml-2">
                  Last checked: {new Date(sub.last_checked).toLocaleString()}
                </span>
              )}
            </CardContent>
          </Card>
        ))}
        {/* 列表为空时的提示信息 */}
        {subscriptions.length === 0 && (
          <p className="text-muted-foreground col-span-full text-center py-12">
            暂无订阅内容。请先添加插件实例，再订阅具体内容。
          </p>
        )}
      </div>
    </div>
  );
}
