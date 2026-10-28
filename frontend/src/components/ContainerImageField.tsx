import { useEffect, useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useImageTags } from "@/hooks/useDocker";
import { formatBytes, formatRelativeTime } from "@/lib/utils";
import { ChevronDown, Loader2 } from "lucide-react";

export interface ContainerImageConfig {
  repository: string;
  tag: string;
}

function splitImageReference(image: string): {
  repository: string;
  tag: string | null;
} {
  const value = image.trim();
  const lastSlash = value.lastIndexOf("/");
  const lastColon = value.lastIndexOf(":");
  if (lastColon > lastSlash) {
    return {
      repository: value.slice(0, lastColon),
      tag: value.slice(lastColon + 1),
    };
  }
  return { repository: value, tag: null };
}

/** 标签在下拉中的展示文本：名称 · 大小 · 推送时间 */
function formatTagLabel(tag: {
  name: string;
  size: number;
  last_updated: string;
}): string {
  const parts = [tag.name];
  if (tag.size > 0) parts.push(formatBytes(tag.size));
  if (tag.last_updated) parts.push(formatRelativeTime(tag.last_updated));
  return parts.join(" · ");
}

interface ContainerImageFieldProps {
  containerName: string;
  defaultImage: string;
  value?: ContainerImageConfig;
  onChange: (value: ContainerImageConfig) => void;
}

export function ContainerImageField({
  containerName,
  defaultImage,
  value,
  onChange,
}: ContainerImageFieldProps) {
  const parsedDefault = splitImageReference(defaultImage);
  const current = value || {
    repository: parsedDefault.repository,
    tag: parsedDefault.tag || "latest",
  };
  const [queryRepository, setQueryRepository] = useState(
    parsedDefault.repository
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      setQueryRepository(splitImageReference(current.repository).repository);
    }, 400);
    return () => clearTimeout(timer);
  }, [current.repository]);

  const { data: imageTags = [], isLoading, refetch } = useImageTags(queryRepository);
  const repositoryId = `image-repository-${containerName}`;
  const tagId = `image-tag-${containerName}`;

  // latest 置顶，其余按推送时间倒序
  const sortedTags = useMemo(
    () =>
      [...imageTags].sort((a, b) => {
        const aLatest = a.name === "latest" ? 1 : 0;
        const bLatest = b.name === "latest" ? 1 : 0;
        if (aLatest !== bLatest) return bLatest - aLatest;
        return (
          new Date(b.last_updated || 0).getTime() -
          new Date(a.last_updated || 0).getTime()
        );
      }),
    [imageTags]
  );

  const tagInList = sortedTags.some((tag) => tag.name === current.tag);
  const empty = !isLoading && sortedTags.length === 0;

  return (
    <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_260px]">
      <div className="space-y-1">
        <Label htmlFor={repositoryId} className="text-xs font-medium">
          镜像地址
          <span className="ml-0.5 text-destructive" aria-hidden="true">*</span>
        </Label>
        <Input
          id={repositoryId}
          value={current.repository}
          onChange={(event) =>
            onChange({ repository: event.target.value, tag: current.tag })
          }
          onBlur={() => {
            const parsed = splitImageReference(current.repository);
            onChange({
              repository: parsed.repository,
              tag: parsed.tag || current.tag.trim(),
            });
          }}
          placeholder="如：jellyfin/jellyfin"
          autoComplete="off"
          className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={tagId} className="text-xs font-medium">
          镜像标签
          <span className="ml-0.5 text-destructive" aria-hidden="true">*</span>
        </Label>
        <div className="relative">
          <select
            id={tagId}
            value={current.tag}
            onChange={(event) => {
              if (event.target.value === "__retry__") {
                void refetch();
                return;
              }
              onChange({
                repository: current.repository,
                tag: event.target.value,
              });
            }}
            title={current.tag || "镜像标签"}
            className="h-8 w-full appearance-none rounded-md border border-input bg-white pl-2 pr-8 text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {!current.tag && <option value="">请选择标签</option>}
            {current.tag && !tagInList && (
              <option value={current.tag}>{current.tag}</option>
            )}
            {sortedTags.map((tag) => (
              <option key={tag.name} value={tag.name}>
                {formatTagLabel(tag)}
              </option>
            ))}
            {empty && <option value="__retry__">未获取到标签，点击重试</option>}
          </select>
          {isLoading ? (
            <Loader2 className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
          ) : (
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          )}
        </div>
        {empty && (
          <p className="text-[11px] text-muted-foreground">
            可能是网络异常或 Docker Hub 限流，在下方选择可重新获取
          </p>
        )}
      </div>
    </div>
  );
}
