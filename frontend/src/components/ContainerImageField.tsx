import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useImageTags } from "@/hooks/useDocker";

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

  const { data: imageTags = [], isLoading } = useImageTags(queryRepository);
  const repositoryId = `image-repository-${containerName}`;
  const tagId = `image-tag-${containerName}`;

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
        <select
          id={tagId}
          value={current.tag}
          disabled={isLoading || imageTags.length === 0}
          onChange={(event) =>
            onChange({ repository: current.repository, tag: event.target.value })
          }
          title={current.tag || "镜像标签"}
          className="flex h-8 w-full rounded-md border border-input bg-white px-2 py-1 text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
        >
          {!current.tag && <option value="">请选择标签</option>}
          {current.tag && !imageTags.some((tag) => tag.name === current.tag) && (
            <option value={current.tag}>{current.tag}</option>
          )}
          {imageTags.map((tag) => (
            <option key={tag.name} value={tag.name}>
              {tag.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
