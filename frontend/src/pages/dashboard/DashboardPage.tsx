/**
 * 仪表盘页面
 *
 * 展示 NAS 的真实运行概览（数据来自 Docker / Compose hooks）：
 * - 统计卡片：容器、镜像、编排项目、Docker 引擎
 * - 宿主机资源：CPU、内存、磁盘
 * - 最近容器列表
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PageHeader } from "@/components/PageHeader";
import {
  useContainers,
  useImages,
  useDockerHostInfo,
  useDockerStatus,
  type ContainerInfo,
} from "@/hooks/useDocker";
import { useComposeProjects } from "@/hooks/useCompose";
import { formatBytes, formatRelativeTime } from "@/lib/utils";
import {
  Box,
  HardDrive,
  Image as ImageIcon,
  Layers,
  Cpu,
  MemoryStick,
  Server,
} from "lucide-react";

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <Card className="rounded-xl">
      <CardContent className="p-4 flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-lg font-semibold leading-tight truncate">{value}</p>
          {sub && (
            <p className="text-xs text-muted-foreground truncate">{sub}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function containerStatusVariant(status: string) {
  switch (status) {
    case "running":
      return "default";
    case "exited":
      return "secondary";
    case "paused":
      return "outline";
    case "dead":
      return "destructive";
    default:
      return "outline";
  }
}

export function DashboardPage() {
  const { data: dockerStatus } = useDockerStatus();
  const { data: containers = [] } = useContainers();
  const { data: images = [] } = useImages();
  const { data: projects = [] } = useComposeProjects();
  const { data: hostInfo } = useDockerHostInfo();

  const dockerAvailable = dockerStatus?.available !== false;

  const runningContainers = containers.filter(
    (c) => c.status.toLowerCase() === "running"
  );
  const totalImageSize = images.reduce((sum, img) => sum + (img.size || 0), 0);
  const activeProjects = projects.filter((p) => p.is_active);
  const recentContainers: ContainerInfo[] = [...containers]
    .sort((a, b) => (b.created || "").localeCompare(a.created || ""))
    .slice(0, 6);

  if (!dockerAvailable) {
    return (
      <div>
        <PageHeader title="仪表盘" description="系统运行概览" />
        <p className="text-muted-foreground">Docker 不可用或未连接。</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader title="仪表盘" description="系统运行概览" />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard
          icon={Box}
          label="容器"
          value={`${runningContainers.length} / ${containers.length}`}
          sub="运行中 / 总数"
        />
        <StatCard
          icon={ImageIcon}
          label="镜像"
          value={images.length}
          sub={`占用 ${formatBytes(totalImageSize)}`}
        />
        <StatCard
          icon={Layers}
          label="编排项目"
          value={projects.length}
          sub={`${activeProjects.length} 个启用中`}
        />
        <StatCard
          icon={Server}
          label="Docker 引擎"
          value={hostInfo?.docker_version?.version ?? "-"}
          sub={hostInfo ? `${hostInfo.os} · ${hostInfo.arch}` : undefined}
        />
      </div>

      {/* 宿主机资源 */}
      {hostInfo && (
        <Card className="rounded-xl">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              宿主机资源
              <span className="text-xs font-normal text-muted-foreground">
                {hostInfo.hostname}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center gap-3">
                <Cpu className="h-4 w-4 text-muted-foreground shrink-0" />
                <div>
                  <p className="text-xs text-muted-foreground">CPU</p>
                  <p className="text-sm font-medium">
                    {hostInfo.resources.cpu_cores} 核
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <MemoryStick className="h-4 w-4 text-muted-foreground shrink-0" />
                <div>
                  <p className="text-xs text-muted-foreground">内存</p>
                  <p className="text-sm font-medium">
                    {formatBytes(hostInfo.resources.memory_total)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <HardDrive className="h-4 w-4 text-muted-foreground shrink-0" />
                <div>
                  <p className="text-xs text-muted-foreground">磁盘</p>
                  <p className="text-sm font-medium">
                    {formatBytes(hostInfo.resources.disk_used)} /{" "}
                    {formatBytes(hostInfo.resources.disk_total)}
                  </p>
                </div>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>磁盘使用率</span>
                <span>{hostInfo.resources.disk_usage_percent.toFixed(1)}%</span>
              </div>
              <Progress
                value={hostInfo.resources.disk_usage_percent}
                className="h-1.5"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* 最近容器 */}
      <Card className="rounded-xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Box className="h-4 w-4 text-muted-foreground" />
            最近容器
          </CardTitle>
        </CardHeader>
        <CardContent>
          {recentContainers.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              暂无容器
            </p>
          ) : (
            <div className="divide-y">
              {recentContainers.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0"
                >
                  <span className="text-sm font-medium truncate flex-1">
                    {c.name}
                  </span>
                  <span className="text-xs text-muted-foreground truncate hidden sm:block max-w-[240px]">
                    {c.image}
                  </span>
                  <Badge
                    variant={containerStatusVariant(c.status)}
                    className="text-xs shrink-0"
                  >
                    {c.state || c.status}
                  </Badge>
                  <span className="text-xs text-muted-foreground shrink-0 hidden md:block">
                    {formatRelativeTime(c.created)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
