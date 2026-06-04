/**
 * Docker 容器管理页面组件
 *
 * 展示所有 Docker 容器的状态信息，包括：
 * - 容器名称和运行状态（绿色=运行中，红色=已停止，黄色=其他）
 * - 容器镜像名称和健康检查状态
 * - 启动、停止、重启操作按钮
 *
 * 当 Docker 不可用或未连接时显示提示信息。
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
import { Play, Square, RotateCcw } from "lucide-react";
import { useContainers, useContainerAction, useDockerStatus } from "@/hooks/useDocker";

/**
 * 容器状态指示点组件
 *
 * 根据容器运行状态显示不同颜色的圆点：
 * - running（运行中）：绿色
 * - exited（已停止）：红色
 * - 其他状态：黄色
 *
 * @param props.status - 容器状态字符串，如 "running"、"exited" 等
 */
function StatusDot({ status }: { status: string }) {
  // 根据状态选择对应的颜色样式
  const color =
    status === "running"
      ? "bg-green-500"
      : status === "exited"
      ? "bg-red-500"
      : "bg-yellow-500";
  // 渲染一个圆形状态指示点
  return <span className={`inline-block w-2 h-2 rounded-full ${color} mr-2`} />;
}

/**
 * Docker 容器管理页面组件
 *
 * 获取 Docker 连接状态和容器列表数据。
 * 若 Docker 不可用则显示提示；否则以卡片网格形式展示每个容器的
 * 名称、状态、镜像、健康信息，以及启动/停止/重启操作按钮。
 */
export function DockerPage() {
  // 获取 Docker 连接状态（是否可用）
  const { data: dockerStatus } = useDockerStatus();
  // 获取所有容器列表，默认为空数组
  const { data: containers = [] } = useContainers();
  // 获取容器操作（启动/停止/重启）的 mutation
  const action = useContainerAction();

  // Docker 不可用或未连接时，显示提示信息
  if (dockerStatus && !dockerStatus.available) {
    return (
      <div>
        <PageHeader title="Docker 管理" />
        <p className="text-muted-foreground">Docker 不可用或未连接。</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Docker 管理" description="管理所有 Docker 容器的运行状态" />
      {/* 容器卡片网格，响应式布局：1列(小屏) -> 2列(中屏) -> 3列(大屏) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 遍历容器列表，渲染每个容器卡片 */}
        {containers.map((c) => (
          <Card key={c.id} className="rounded-xl">
            {/* 卡片头部：状态指示点 + 容器名称 */}
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center">
                <StatusDot status={c.status} />
                {c.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* 镜像名称和健康状态徽章 */}
              <div className="flex gap-2">
                {/* 镜像名称标签 */}
                <Badge variant="outline" className="text-xs">
                  {c.image}
                </Badge>
                {/* 健康状态标签，仅在非 "unknown" 时显示 */}
                {c.health !== "unknown" && (
                  <Badge
                    variant={c.health === "healthy" ? "default" : "destructive"}
                    className="text-xs"
                  >
                    {c.health}
                  </Badge>
                )}
              </div>
              {/* 容器操作按钮组 */}
              <div className="flex gap-1">
                {/* 启动按钮，仅在容器未运行时可点击 */}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => action.mutate({ id: c.id, action: "start" })}
                  disabled={c.status === "running"}
                >
                  <Play className="h-3 w-3" />
                </Button>
                {/* 停止按钮，仅在容器运行中时可点击 */}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => action.mutate({ id: c.id, action: "stop" })}
                  disabled={c.status !== "running"}
                >
                  <Square className="h-3 w-3" />
                </Button>
                {/* 重启按钮，任何时候都可点击 */}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => action.mutate({ id: c.id, action: "restart" })}
                >
                  <RotateCcw className="h-3 w-3" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {/* 容器列表为空时的提示 */}
        {containers.length === 0 && (
          <p className="text-muted-foreground col-span-full text-center py-12">
            暂无容器。
          </p>
        )}
      </div>
    </div>
  );
}
