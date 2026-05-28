/**
 * 通知中心页面组件（占位页）
 *
 * 尚未实现完整功能，目前仅展示一个通知历史的占位卡片。
 * 未来将用于展示所有通知的发送历史记录。
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * 通知中心页面组件
 *
 * 当前为占位实现，仅渲染一个标题和一个"通知历史"卡片，
 * 卡片内显示"通知历史将在此显示"的提示文字。
 * 完整的通知列表、筛选、详情查看等功能待后续开发。
 */
export function NotificationsPage() {
  return (
    <div>
      {/* 页面标题 */}
      <h2 className="text-2xl font-bold mb-6">通知中心</h2>
      {/* 通知历史占位卡片 */}
      <Card className="rounded-xl">
        <CardHeader>
          <CardTitle className="text-base">通知历史</CardTitle>
        </CardHeader>
        <CardContent>
          {/* 占位提示文字 */}
          <p className="text-muted-foreground text-sm">
            通知历史将在此显示。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
