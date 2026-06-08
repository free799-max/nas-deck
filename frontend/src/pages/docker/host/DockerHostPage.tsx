/**
 * Docker 宿主机信息页面组件
 *
 * 展示 Docker 宿主机的综合信息，包括：
 * - 主机概览（主机名、OS、架构、内核版本）
 * - Docker 引擎信息（版本、API 版本、存储驱动、根目录）
 * - 资源概览（CPU 核心数、内存总量、磁盘使用）
 * - Docker 统计（容器总数/运行中/暂停/已停止、镜像数量）
 * - Docker 网络列表
 *
 * 当 Docker 不可用或未连接时显示提示信息。
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDockerHostInfo, useDockerStatus } from "@/hooks/useDocker";
import { PageHeader } from "@/components/PageHeader";
import { formatBytes } from "@/lib/utils";
import { InfoRow } from "../shared/InfoRow";
import {
  Monitor,
  Cpu,
  MemoryStick,
  HardDrive,
  Box,
  Play,
  Pause,
  Square,
  Image,
  Network,
  Server,
} from "lucide-react";

/**
 * Docker 宿主机信息页面组件
 */
export function DockerHostPage() {
  const { data: dockerStatus } = useDockerStatus();
  const { data: hostInfo, isLoading } = useDockerHostInfo();

  // 加载中状态（优先判断，避免闪烁）
  if (isLoading) {
    return (
      <div>
        <PageHeader title="Docker 主机" />
        <p className="text-muted-foreground">加载中...</p>
      </div>
    );
  }

  // Docker 不可用或未连接时，显示提示信息
  if (dockerStatus && !dockerStatus.available) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6">Docker 主机</h2>
        <p className="text-muted-foreground">Docker 不可用或未连接。</p>
      </div>
    );
  }

  if (!hostInfo) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6">Docker 主机</h2>
        <p className="text-muted-foreground">无法获取主机信息。</p>
      </div>
    );
  }

  const { resources, stats, docker_version } = hostInfo;

  return (
    <div>
      <PageHeader title="Docker 主机" description="查看 Docker 宿主机综合信息" />

      {/* 第一行：主机概览 + Docker 引擎 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* 主机概览 */}
        <Card className="rounded-xl">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Monitor className="h-4 w-4 text-muted-foreground" />
              主机概览
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold mb-3">{hostInfo.hostname}</div>
            <InfoRow label="操作系统" value={`${hostInfo.os} (${hostInfo.arch})`} />
            <InfoRow label="内核版本" value={hostInfo.kernel_version} />
            <InfoRow label="存储驱动" value={hostInfo.storage_driver} />
          </CardContent>
        </Card>

        {/* Docker 引擎 */}
        <Card className="rounded-xl">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Server className="h-4 w-4 text-muted-foreground" />
              Docker 引擎
            </CardTitle>
          </CardHeader>
          <CardContent>
            <InfoRow label="引擎版本" value={docker_version.version} />
            <InfoRow label="API 版本" value={docker_version.api_version} />
            <InfoRow label="Go 版本" value={docker_version.go_version} />
            <InfoRow label="存储驱动" value={hostInfo.storage_driver} />
            <InfoRow label="根目录" value={hostInfo.docker_root_dir} />
          </CardContent>
        </Card>
      </div>

      {/* 第二行：资源概览（3 列） */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        {/* CPU */}
        <Card className="rounded-xl">
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-lg bg-muted">
                <Cpu className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm text-muted-foreground">CPU</div>
                <div className="text-xl font-bold">{resources.cpu_cores} 核</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 内存 */}
        <Card className="rounded-xl">
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-lg bg-muted">
                <MemoryStick className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm text-muted-foreground">内存</div>
                <div className="text-xl font-bold">
                  {formatBytes(resources.memory_total)}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 磁盘 */}
        <Card className="rounded-xl">
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-lg bg-muted">
                <HardDrive className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm text-muted-foreground">磁盘</div>
                <div className="text-xl font-bold">
                  {formatBytes(resources.disk_total)}
                </div>
              </div>
            </div>
            {/* 磁盘使用进度条 */}
            <div className="mt-2">
              {resources.disk_total === 0 ? (
                <p className="text-xs text-muted-foreground">无法获取磁盘信息</p>
              ) : (
                <>
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>已用 {formatBytes(resources.disk_used)}</span>
                    <span>{resources.disk_usage_percent}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${resources.disk_usage_percent}%` }}
                    />
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 第三行：Docker 统计（5 列小卡片） */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
        {/* 容器总数 */}
        <Card className="rounded-xl">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-2">
              <Box className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">容器总数</span>
            </div>
            <div className="text-2xl font-bold">{stats.containers_total}</div>
          </CardContent>
        </Card>

        {/* 运行中 */}
        <Card className="rounded-xl">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-2">
              <Play className="h-4 w-4 text-green-500" />
              <span className="text-xs text-muted-foreground">运行中</span>
            </div>
            <div className="text-2xl font-bold">{stats.containers_running}</div>
          </CardContent>
        </Card>

        {/* 暂停 */}
        <Card className="rounded-xl">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-2">
              <Pause className="h-4 w-4 text-yellow-500" />
              <span className="text-xs text-muted-foreground">暂停</span>
            </div>
            <div className="text-2xl font-bold">{stats.containers_paused}</div>
          </CardContent>
        </Card>

        {/* 已停止 */}
        <Card className="rounded-xl">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-2">
              <Square className="h-4 w-4 text-red-500" />
              <span className="text-xs text-muted-foreground">已停止</span>
            </div>
            <div className="text-2xl font-bold">{stats.containers_stopped}</div>
          </CardContent>
        </Card>

        {/* 镜像数量 */}
        <Card className="rounded-xl">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-2">
              <Image className="h-4 w-4 text-blue-500" />
              <span className="text-xs text-muted-foreground">镜像</span>
            </div>
            <div className="text-2xl font-bold">{stats.images}</div>
          </CardContent>
        </Card>
      </div>

      {/* 第四行：Docker 网络列表 */}
      <Card className="rounded-xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Network className="h-4 w-4 text-muted-foreground" />
            Docker 网络
          </CardTitle>
        </CardHeader>
        <CardContent>
          {hostInfo.networks.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无网络。</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">名称</TableHead>
                  <TableHead className="text-xs">驱动</TableHead>
                  <TableHead className="text-xs">作用域</TableHead>
                  <TableHead className="text-xs">ID</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hostInfo.networks.map((net) => (
                  <TableRow key={net.id}>
                    <TableCell className="text-sm font-medium">
                      {net.name}
                    </TableCell>
                    <TableCell className="text-sm">{net.driver}</TableCell>
                    <TableCell className="text-sm">{net.scope}</TableCell>
                    <TableCell className="text-sm text-muted-foreground font-mono">
                      {net.id}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
