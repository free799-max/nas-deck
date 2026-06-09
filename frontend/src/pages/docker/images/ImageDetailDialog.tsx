/**
 * 镜像详情弹窗组件
 *
 * Tab 切换展示镜像元数据：基本信息、配置、层。
 */

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useImageDetail, type ImageDetail } from "@/hooks/useDocker";
import { formatBytes, formatDate } from "@/lib/utils";
import {
  Loader2,
  Copy,
  Check,
  Layers,
  Settings,
  Info,
} from "lucide-react";

interface ImageDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  imageId: string | null;
}

type TabKey = "info" | "config" | "layers";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <Button
      size="icon"
      variant="ghost"
      className="h-6 w-6 ml-1"
      onClick={handleCopy}
    >
      {copied ? (
        <Check className="h-3 w-3 text-green-500" />
      ) : (
        <Copy className="h-3 w-3" />
      )}
    </Button>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-1.5 border-b last:border-0">
      <span className="text-sm text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm text-right break-all">{value}</span>
    </div>
  );
}

function TabButton({
  active,
  label,
  icon: Icon,
  onClick,
}: {
  active: boolean;
  label: string;
  icon: React.ElementType;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md transition-colors ${
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:text-foreground hover:bg-muted"
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

function InfoTab({ detail }: { detail: ImageDetail }) {
  return (
    <div className="space-y-1">
      <InfoRow
        label="完整 ID"
        value={
          <span className="font-mono text-xs flex items-center justify-end">
            {detail.id}
            <CopyButton text={detail.id} />
          </span>
        }
      />
      <InfoRow label="名称" value={detail.name} />
      <InfoRow
        label="标签"
        value={<Badge variant="outline">{detail.tag}</Badge>}
      />
      <InfoRow label="完整标签" value={detail.full_tag} />
      <InfoRow label="大小" value={formatBytes(detail.size)} />
      <InfoRow label="创建时间" value={formatDate(detail.created)} />
      <InfoRow label="架构" value={detail.architecture} />
      <InfoRow label="操作系统" value={detail.os} />
    </div>
  );
}

function ConfigTab({ detail }: { detail: ImageDetail }) {
  return (
    <div className="space-y-3">
      {detail.cmd && (
        <div>
          <span className="text-xs text-muted-foreground block mb-1">命令 (Cmd)</span>
          <code className="text-xs bg-muted px-2 py-1 rounded block break-all">
            {JSON.stringify(detail.cmd)}
          </code>
        </div>
      )}
      {detail.entrypoint && (
        <div>
          <span className="text-xs text-muted-foreground block mb-1">入口点 (Entrypoint)</span>
          <code className="text-xs bg-muted px-2 py-1 rounded block break-all">
            {JSON.stringify(detail.entrypoint)}
          </code>
        </div>
      )}
      {detail.env && detail.env.length > 0 && (
        <div>
          <span className="text-xs text-muted-foreground block mb-1">环境变量</span>
          <div className="space-y-1">
            {detail.env.map((e) => (
              <code
                key={e}
                className="text-xs bg-muted px-2 py-1 rounded block break-all"
              >
                {e}
              </code>
            ))}
          </div>
        </div>
      )}
      {detail.exposed_ports && detail.exposed_ports.length > 0 && (
        <div>
          <span className="text-xs text-muted-foreground block mb-1">暴露端口</span>
          <div className="flex flex-wrap gap-1">
            {detail.exposed_ports.map((p) => (
              <Badge key={p} variant="outline" className="text-xs">
                {p}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {detail.volumes && detail.volumes.length > 0 && (
        <div>
          <span className="text-xs text-muted-foreground block mb-1">卷</span>
          <div className="space-y-1">
            {detail.volumes.map((v) => (
              <code
                key={v}
                className="text-xs bg-muted px-2 py-1 rounded block break-all"
              >
                {v}
              </code>
            ))}
          </div>
        </div>
      )}
      {detail.working_dir && (
        <InfoRow label="工作目录" value={detail.working_dir} />
      )}
      {detail.user && <InfoRow label="运行用户" value={detail.user} />}
      {detail.labels && Object.keys(detail.labels).length > 0 && (
        <div>
          <span className="text-xs text-muted-foreground block mb-1">标签 (Labels)</span>
          <div className="space-y-1">
            {Object.entries(detail.labels).map(([k, v]) => (
              <div
                key={k}
                className="flex justify-between text-xs bg-muted px-2 py-1 rounded"
              >
                <span className="text-muted-foreground shrink-0 mr-2">{k}</span>
                <span className="break-all text-right">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function LayersTab({ detail }: { detail: ImageDetail }) {
  return (
    <div className="space-y-3">
      {detail.history && detail.history.length > 0 && (
        <div>
          <span className="text-xs text-muted-foreground block mb-2">
            构建历史 ({detail.history.length} 条)
          </span>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {detail.history.map((h, i) => (
              <div
                key={i}
                className="text-xs bg-muted px-2 py-1.5 rounded break-all"
              >
                {h}
              </div>
            ))}
          </div>
        </div>
      )}
      {detail.layers && detail.layers.length > 0 && (
        <div>
          <span className="text-xs text-muted-foreground block mb-2">
            镜像层 ({detail.layers.length} 层)
          </span>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {detail.layers.map((layer, i) => (
              <div
                key={i}
                className="flex items-center justify-between text-xs bg-muted px-2 py-1.5 rounded"
              >
                <span className="font-mono break-all mr-2">{layer}</span>
                <CopyButton text={layer} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ImageDetailDialog({
  open,
  onOpenChange,
  imageId,
}: ImageDetailDialogProps) {
  const [tab, setTab] = useState<TabKey>("info");
  const { data: detail, isLoading } = useImageDetail(imageId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-base">镜像详情</DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : !detail ? (
          <p className="text-muted-foreground text-center py-12">无法加载镜像详情</p>
        ) : (
          <>
            <div className="flex gap-1 mb-4 shrink-0">
              <TabButton
                active={tab === "info"}
                label="基本信息"
                icon={Info}
                onClick={() => setTab("info")}
              />
              <TabButton
                active={tab === "config"}
                label="配置"
                icon={Settings}
                onClick={() => setTab("config")}
              />
              <TabButton
                active={tab === "layers"}
                label="层"
                icon={Layers}
                onClick={() => setTab("layers")}
              />
            </div>
            <div className="overflow-y-auto pr-1">
              {tab === "info" && <InfoTab detail={detail} />}
              {tab === "config" && <ConfigTab detail={detail} />}
              {tab === "layers" && <LayersTab detail={detail} />}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
