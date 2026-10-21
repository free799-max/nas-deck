/**
 * 数据目录路径输入组件
 *
 * 结构：目录来源下拉 + 子路径输入框 + 浏览按钮。
 * 值约定（受控 value/onChange 传完整路径字符串）：
 * - 选中存储目录（含应用数据目录）：value = `mount_path/子路径`（容器视角绝对路径）
 * - 无法匹配任何已配置目录的存量值：显示「自定义路径」，原样保留不静默改写
 *   （手输路径由后端部署校验兜底）
 */

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { DirectoryPicker } from "@/components/DirectoryPicker";
import type { StorageDirectory } from "@/api/settings";
import {
  useSettingsDirectories,
  useSettingsCreateDirectory,
  useSettingsRenameDirectory,
  useSettingsDeleteDirectory,
} from "@/hooks/useSettings";
import { FolderOpen } from "lucide-react";

/** 下拉中「自定义路径」选项的值（仅存量值无法匹配已配置目录时出现） */
const CUSTOM_SOURCE = "__custom__";

/** 目录来源解析结果 */
type ParsedSource =
  | { kind: "app"; dir: StorageDirectory; subPath: string }
  | { kind: "storage"; dir: StorageDirectory; subPath: string }
  | { kind: "custom" };

/** 去掉路径末尾多余的斜杠 */
function trimTrailingSlash(path: string): string {
  return path.replace(/\/+$/, "") || "/";
}

/** 判断 value 是否等于 base 或位于 base 之下，是则返回剩余子路径 */
function matchPrefix(value: string, base: string): string | null {
  const normalizedBase = trimTrailingSlash(base);
  if (!normalizedBase || normalizedBase === "/") return null;
  if (value === normalizedBase) return "";
  if (value.startsWith(`${normalizedBase}/`)) {
    return value.slice(normalizedBase.length + 1);
  }
  return null;
}

/** 解析当前值所属的目录来源（应用数据目录按 is_app_data 记录的 mount_path 前缀匹配） */
function parseSource(
  value: string,
  appDataDir: StorageDirectory | null,
  storageDirectories: StorageDirectory[]
): ParsedSource {
  if (value.startsWith("/")) {
    // 优先匹配挂载路径最长的目录（应用数据目录与普通数据目录一同参与匹配）
    const candidates = appDataDir
      ? [appDataDir, ...storageDirectories]
      : storageDirectories;
    const sorted = [...candidates].sort(
      (a, b) => b.mount_path.length - a.mount_path.length
    );
    for (const dir of sorted) {
      const sub = matchPrefix(value, dir.mount_path);
      if (sub !== null) {
        return dir.is_app_data
          ? { kind: "app", dir, subPath: sub }
          : { kind: "storage", dir, subPath: sub };
      }
    }
  }
  // 绝对路径未匹配任何已配置目录，或存量相对路径值：按自定义路径原样保留
  return { kind: "custom" };
}

interface DataDirPathInputProps {
  id?: string;
  /** 完整路径字符串 */
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** 应用数据目录（is_app_data 的启用记录）；为 null 时不提供该来源选项 */
  appDataDir: StorageDirectory | null;
  /** 已启用的普通数据目录列表 */
  storageDirectories: StorageDirectory[];
}

export function DataDirPathInput({
  id,
  value,
  onChange,
  placeholder,
  appDataDir,
  storageDirectories,
}: DataDirPathInputProps) {
  const [pickerOpen, setPickerOpen] = useState(false);

  // 目录浏览/新建/重命名/删除统一走设置端点（后端容器内视角）
  const settingsCreateDirectory = useSettingsCreateDirectory();
  const settingsRenameDirectory = useSettingsRenameDirectory();
  const settingsDeleteDirectory = useSettingsDeleteDirectory();

  const source = useMemo(
    () => parseSource(value, appDataDir, storageDirectories),
    [value, appDataDir, storageDirectories]
  );

  const selectValue =
    source.kind === "custom" ? CUSTOM_SOURCE : source.kind === "app" ? "app" : String(source.dir.id);

  // 子路径输入框展示值：自定义模式展示原始值（不静默改写），
  // 存储目录/应用数据目录模式展示去掉 mount_path 前缀后的子路径
  const subPath = source.kind === "custom" ? value : source.subPath;

  /** 由来源与子路径拼装完整 value */
  const buildValue = (nextSource: string, nextSub: string): string => {
    const sub = nextSub.replace(/^\/+/, "");
    const dir =
      nextSource === "app"
        ? appDataDir
        : storageDirectories.find((d) => String(d.id) === nextSource);
    if (!dir) return nextSub;
    const base = trimTrailingSlash(dir.mount_path);
    return sub ? `${base}/${sub}` : base;
  };

  const handleSourceChange = (nextSource: string) => {
    if (nextSource === CUSTOM_SOURCE) return;
    // 切换来源时保留已有子路径；自定义绝对路径无法表达为新来源的子路径，清空待重新选择
    const currentSub = source.kind === "custom" ? "" : source.subPath;
    onChange(buildValue(nextSource, currentSub));
  };

  const handleSubPathChange = (nextSub: string) => {
    if (source.kind === "custom") {
      // 自定义路径：子路径输入框即完整值，原样保留
      onChange(nextSub);
      return;
    }
    onChange(buildValue(selectValue, nextSub));
  };

  const currentDir = source.kind === "custom" ? null : source.dir;

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <select
          aria-label="目录来源"
          value={selectValue}
          onChange={(e) => handleSourceChange(e.target.value)}
          className="h-8 w-44 shrink-0 rounded-md border border-input bg-white px-2 py-1 text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          {appDataDir && (
            <option value="app">应用数据目录（{appDataDir.mount_path}）</option>
          )}
          {storageDirectories.map((dir) => (
            <option key={dir.id} value={String(dir.id)}>
              {dir.name}（{dir.mount_path}）
            </option>
          ))}
          {source.kind === "custom" && (
            <option value={CUSTOM_SOURCE}>自定义路径</option>
          )}
        </select>
        <Input
          id={id}
          type="text"
          value={subPath}
          onChange={(e) => handleSubPathChange(e.target.value)}
          placeholder={
            source.kind === "custom"
              ? placeholder
              : "子路径（留空则为目录根）"
          }
          className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
        />
        <Button
          type="button"
          variant="secondary"
          size="icon"
          className="h-8 w-8 shrink-0 rounded-md"
          onClick={() => setPickerOpen(true)}
          title="选择目录"
        >
          <FolderOpen className="h-4 w-4" />
        </Button>
      </div>
      {source.kind === "custom" && value && (
        <p className="text-xs text-amber-600">
          该路径不在已配置的数据目录下，可在「系统设置 → 存储配置」中添加对应目录后重新选择。
        </p>
      )}
      {currentDir && !currentDir.visible && (
        <p className="text-xs text-amber-600">
          该目录在后端容器内不可见，无法浏览子目录，请将宿主机路径挂载进后端容器。
        </p>
      )}

      <DirectoryPicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        rootPath={currentDir ? currentDir.mount_path : "/"}
        initialPath={
          value.startsWith("/") ? value : currentDir?.mount_path
        }
        returnRelative={false}
        onSelect={(path) => onChange(path)}
        useDirectoriesQuery={useSettingsDirectories}
        createDirectory={settingsCreateDirectory}
        renameDirectory={settingsRenameDirectory}
        deleteDirectory={settingsDeleteDirectory}
      />
    </div>
  );
}
