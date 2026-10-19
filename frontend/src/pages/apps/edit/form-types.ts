/**
 * 应用创建/编辑表单状态与转换工具
 */

import type { AppDetail } from "@/api/apps";

/** 默认端口编辑行 */
export interface PortRow {
  port: number;
  protocol: string;
  description: string;
}

/** 表单状态：config_schema / yaml_template 等以文本形式编辑，保存时转换 */
export interface AppFormState {
  name: string;
  display_name: string;
  description: string;
  category: string;
  /** 逗号分隔的标签文本 */
  tagsText: string;
  icon: string;
  website: string;
  source_url: string;
  architectures: string[];
  image: string;
  default_ports: PortRow[];
  /** 每行一个备份路径 */
  backupPathsText: string;
  configSchemaText: string;
  yamlTemplate: string;
  readme: string;
  version: string;
  type: string;
  changelog: string;
}

/** 架构选项 */
export const ARCH_OPTIONS = ["amd64", "arm64", "arm/v7"];

/** 分类选项（与 AppsTab 的 CATEGORY_LABELS 保持一致） */
export const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "other", label: "其他" },
  { value: "movie", label: "影视" },
  { value: "comic", label: "漫画" },
  { value: "book", label: "书籍" },
  { value: "music", label: "音乐" },
  { value: "game", label: "游戏" },
  { value: "gallery", label: "图库" },
  { value: "news", label: "资讯" },
  { value: "download", label: "下载" },
  { value: "docker", label: "Docker" },
  { value: "tool", label: "工具" },
  { value: "media", label: "媒体" },
  { value: "network", label: "网络" },
  { value: "web", label: "网站" },
];

/** 默认的 config_schema 模板 */
const DEFAULT_CONFIG_SCHEMA = `{
  "type": "object",
  "properties": {}
}`;

/** 默认的 yaml_template 模板 */
const DEFAULT_YAML_TEMPLATE = `services:
  app:
    image: {{ image }}
    container_name: {{ project_name }}
    restart: unless-stopped
`;

/** 创建模式的初始表单状态 */
export function emptyFormState(): AppFormState {
  return {
    name: "",
    display_name: "",
    description: "",
    category: "other",
    tagsText: "",
    icon: "",
    website: "",
    source_url: "",
    architectures: ["amd64", "arm64"],
    image: "",
    default_ports: [],
    backupPathsText: "",
    configSchemaText: DEFAULT_CONFIG_SCHEMA,
    yamlTemplate: DEFAULT_YAML_TEMPLATE,
    readme: "",
    version: "1.0.0",
    type: "compose",
    changelog: "",
  };
}

/** 从应用详情初始化表单状态（编辑模式） */
export function formStateFromApp(app: AppDetail): AppFormState {
  return {
    name: app.name,
    display_name: app.display_name,
    description: app.description ?? "",
    category: app.category || "other",
    tagsText: app.tags.join(", "),
    icon: app.icon ?? "",
    website: app.website ?? "",
    source_url: app.source_url ?? "",
    architectures: app.architectures ?? [],
    image: app.image ?? "",
    default_ports: (app.default_ports ?? []).map((p) => ({
      port: p.port,
      protocol: p.protocol ?? "tcp",
      description: p.description ?? "",
    })),
    backupPathsText: (app.backup_paths ?? []).join("\n"),
    configSchemaText: JSON.stringify(app.config_schema ?? {}, null, 2),
    yamlTemplate: app.yaml_template ?? "",
    readme: app.readme ?? "",
    version: app.version || "1.0.0",
    type: app.type || "compose",
    changelog: app.changelog ?? "",
  };
}

/** 将标签文本解析为数组 */
export function parseTags(tagsText: string): string[] {
  return tagsText
    .split(/[,，]/)
    .map((t) => t.trim())
    .filter(Boolean);
}

/** 将备份路径文本解析为数组 */
export function parseBackupPaths(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}
