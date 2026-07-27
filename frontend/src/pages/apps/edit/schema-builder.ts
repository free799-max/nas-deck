/**
 * config_schema 可视化构建器的数据模型与转换工具
 *
 * - schemaToBuilderModel: 将 JSON Schema 解析为可视化模型（不支持的结构返回 null）
 * - builderModelToSchema: 将可视化模型序列化回 JSON Schema
 * - generateYamlTemplate: 根据 config_schema 自动生成 Jinja2 Compose 模板
 *
 * 数组字段的 items 结构与内置应用（如 moviepilot）保持一致，
 * 确保部署向导（SchemaForm）与编排共享配置（schema-utils）能正确识别。
 */

/** 可视化构建器支持的字段类型 */
export type BuilderFieldType =
  | "string"
  | "integer"
  | "number"
  | "boolean"
  | "password"
  | "directory"
  | "enum"
  | "ports"
  | "volumes"
  | "env"
  | "devices";

/** 数组字段的默认值行 */
export type BuilderRow = Record<string, string | number>;

export interface BuilderField {
  key: string;
  type: BuilderFieldType;
  title: string;
  description: string;
  required: boolean;
  /** 标量默认值（文本形式，boolean 用 defaultBool） */
  defaultValue: string;
  defaultBool: boolean;
  /** enum 类型的选项 */
  enumOptions: string[];
  /** integer/number 的最小/最大值（空串表示不限制） */
  minimum: string;
  maximum: string;
  /** 数组类型的默认值行 */
  defaultRows: BuilderRow[];
}

export type BuilderSettingType =
  | "ports"
  | "volumes"
  | "env"
  | "devices"
  | "advanced";

export const SETTING_TYPES: BuilderSettingType[] = [
  "ports",
  "volumes",
  "env",
  "devices",
  "advanced",
];

/** 容器分组中各设置块的默认标题（与部署向导展示一致） */
export const SETTING_TITLES: Record<BuilderSettingType, string> = {
  ports: "端口设置",
  volumes: "存储空间设置",
  env: "环境变量",
  devices: "设备映射",
  advanced: "高级设置",
};

export interface BuilderContainer {
  name: string;
  title: string;
  description: string;
  /** 设置块类型 -> 分配的字段名 */
  assignments: Record<BuilderSettingType, string[]>;
}

export interface BuilderModel {
  fields: BuilderField[];
  containers: BuilderContainer[];
}

/** 标准组字段（类型固定，用户不可更改） */
export const FIXED_FIELD_TYPES: {
  type: BuilderFieldType;
  label: string;
  suggestedKey: string;
  suggestedTitle: string;
}[] = [
  { type: "ports", label: "端口映射", suggestedKey: "ports", suggestedTitle: "端口设置" },
  { type: "volumes", label: "挂载目录", suggestedKey: "volumes", suggestedTitle: "存储空间设置" },
  { type: "env", label: "环境变量", suggestedKey: "env", suggestedTitle: "环境变量" },
  { type: "devices", label: "设备映射", suggestedKey: "devices", suggestedTitle: "设备映射" },
];

/** 特权模式固定字段的 key */
export const PRIVILEGED_KEY = "privileged";

/** 自定义字段可选的标量类型（标准组类型不在此列） */
export const SCALAR_FIELD_TYPE_OPTIONS: {
  value: BuilderFieldType;
  label: string;
}[] = [
  { value: "string", label: "文本" },
  { value: "integer", label: "整数（如端口）" },
  { value: "number", label: "数字" },
  { value: "boolean", label: "开关" },
  { value: "password", label: "密码" },
  { value: "directory", label: "目录路径" },
  { value: "enum", label: "下拉选项" },
];

/** 标准组类型的固定显示名 */
export const FIXED_TYPE_LABELS: Partial<Record<BuilderFieldType, string>> = {
  ports: "端口映射",
  volumes: "挂载目录",
  env: "环境变量",
  devices: "设备映射",
};

/** 数组字段类型对应的默认字段名建议 */
export const ARRAY_TYPE_SUGGESTED_KEY: Partial<
  Record<BuilderFieldType, string>
> = {
  ports: "ports",
  volumes: "volumes",
  env: "env",
  devices: "devices",
};

const ARRAY_TYPES: BuilderFieldType[] = ["ports", "volumes", "env", "devices"];

export function isArrayFieldType(type: BuilderFieldType): boolean {
  return ARRAY_TYPES.includes(type);
}

/** 判断字段类型是否可分配到指定设置块 */
export function fieldFitsSetting(
  fieldType: BuilderFieldType,
  settingType: BuilderSettingType
): boolean {
  if (settingType === "advanced") return !isArrayFieldType(fieldType);
  return fieldType === settingType;
}

// ---------------------------------------------------------------------------
// items 模板（与内置应用保持一致）
// ---------------------------------------------------------------------------

function itemsForType(type: BuilderFieldType): Record<string, unknown> {
  switch (type) {
    case "ports":
      return {
        type: "object",
        properties: {
          local_port: {
            type: "integer",
            title: "本地端口",
            minimum: 1,
            maximum: 65535,
          },
          container_port: {
            type: "integer",
            title: "容器端口",
            minimum: 1,
            maximum: 65535,
          },
          protocol: {
            type: "string",
            title: "协议",
            enum: ["tcp", "udp"],
            default: "tcp",
          },
        },
        required: ["local_port", "container_port", "protocol"],
      };
    case "volumes":
      return {
        type: "object",
        properties: {
          host_path: { type: "string", title: "本地路径", format: "directory" },
          container_path: { type: "string", title: "容器路径" },
          mode: {
            type: "string",
            title: "权限",
            enum: ["rw", "ro"],
            default: "rw",
          },
        },
        required: ["host_path", "mode"],
      };
    case "env":
      return {
        type: "object",
        properties: {
          key: { type: "string", title: "变量名" },
          value: { type: "string", title: "值" },
        },
        required: ["key", "value"],
      };
    case "devices":
      return {
        type: "object",
        properties: {
          host_path: { type: "string", title: "宿主机设备" },
          container_path: { type: "string", title: "容器设备" },
        },
        required: ["host_path", "container_path"],
      };
    default:
      return {};
  }
}

/** 各类数组字段的行结构（键、输入类型、选项） */
export const ARRAY_ROW_COLUMNS: Record<
  string,
  { key: string; label: string; input: "text" | "number" | "select"; options?: string[] }[]
> = {
  ports: [
    { key: "local_port", label: "本地端口", input: "number" },
    { key: "container_port", label: "容器端口", input: "number" },
    { key: "protocol", label: "协议", input: "select", options: ["tcp", "udp"] },
  ],
  volumes: [
    { key: "host_path", label: "本地路径", input: "text" },
    { key: "container_path", label: "容器路径", input: "text" },
    { key: "mode", label: "权限", input: "select", options: ["rw", "ro"] },
  ],
  env: [
    { key: "key", label: "变量名", input: "text" },
    { key: "value", label: "值", input: "text" },
  ],
  devices: [
    { key: "host_path", label: "宿主机设备", input: "text" },
    { key: "container_path", label: "容器设备", input: "text" },
  ],
};

export function emptyRowForType(type: BuilderFieldType): BuilderRow {
  switch (type) {
    case "ports":
      return { local_port: 0, container_port: 0, protocol: "tcp" };
    case "volumes":
      return { host_path: "", container_path: "", mode: "rw" };
    case "env":
      return { key: "", value: "" };
    case "devices":
      return { host_path: "", container_path: "" };
    default:
      return {};
  }
}

// ---------------------------------------------------------------------------
// 分类：JSON Schema property -> BuilderFieldType
// ---------------------------------------------------------------------------

type RawProperty = Record<string, unknown>;

function classifyProperty(prop: RawProperty): BuilderFieldType | null {
  if (!prop || typeof prop !== "object") return null;
  const type = prop.type;

  if (type === "array") {
    const items = prop.items as RawProperty | undefined;
    const itemProps = items?.properties as
      | Record<string, unknown>
      | undefined;
    if (!itemProps) return null;
    const keys = Object.keys(itemProps);
    const has = (...names: string[]) =>
      names.every((n) => keys.includes(n));
    if (has("local_port", "container_port")) return "ports";
    // volumes 先于 devices 判断（volumes 多一个 mode 列）
    if (has("host_path", "container_path", "mode")) return "volumes";
    if (has("host_path", "container_path")) return "devices";
    if (has("key", "value")) return "env";
    return null;
  }

  if (type === "boolean") return "boolean";
  if (type === "integer") return "integer";
  if (type === "number") return "number";
  if (type === "string") {
    if (Array.isArray(prop.enum)) return "enum";
    if (prop.format === "password") return "password";
    if (prop.format === "directory") return "directory";
    return "string";
  }
  return null;
}

// ---------------------------------------------------------------------------
// Schema -> Model
// ---------------------------------------------------------------------------

function asString(value: unknown): string {
  if (value === undefined || value === null) return "";
  return String(value);
}

function propertyToField(key: string, prop: RawProperty): BuilderField | null {
  const type = classifyProperty(prop);
  if (!type) return null;

  const field: BuilderField = {
    key,
    type,
    title: asString(prop.title),
    description: asString(prop.description),
    required: false,
    defaultValue: "",
    defaultBool: prop.default === true,
    enumOptions: Array.isArray(prop.enum)
      ? (prop.enum as unknown[]).map((o) => String(o))
      : [],
    minimum: prop.minimum === undefined ? "" : String(prop.minimum),
    maximum: prop.maximum === undefined ? "" : String(prop.maximum),
    defaultRows: [],
  };

  if (isArrayFieldType(type)) {
    const rows = Array.isArray(prop.default) ? prop.default : [];
    const columns = ARRAY_ROW_COLUMNS[type].map((c) => c.key);
    field.defaultRows = rows
      .filter((r) => r && typeof r === "object")
      .map((r) => {
        const src = r as Record<string, unknown>;
        const row: BuilderRow = {};
        for (const col of columns) {
          const v = src[col];
          row[col] = typeof v === "number" ? v : asString(v);
        }
        return row;
      });
  } else if (type !== "boolean") {
    field.defaultValue = asString(prop.default);
  }

  return field;
}

function parseContainer(raw: unknown): BuilderContainer | null {
  if (!raw || typeof raw !== "object") return null;
  const c = raw as Record<string, unknown>;
  if (typeof c.name !== "string" || !c.name) return null;
  const container: BuilderContainer = {
    name: c.name,
    title: asString(c.title),
    description: asString(c.description),
    assignments: {
      ports: [],
      volumes: [],
      env: [],
      devices: [],
      advanced: [],
    },
  };
  const settings = Array.isArray(c.settings) ? c.settings : [];
  for (const s of settings) {
    if (!s || typeof s !== "object") return null;
    const setting = s as Record<string, unknown>;
    const st = setting.type as BuilderSettingType;
    if (!SETTING_TYPES.includes(st)) return null;
    const fields = Array.isArray(setting.fields) ? setting.fields : [];
    container.assignments[st].push(
      ...fields.filter((f): f is string => typeof f === "string")
    );
  }
  return container;
}

/**
 * 将 config_schema 解析为可视化模型。
 * 存在不支持的字段结构时返回 null（调用方应回退到源码编辑）。
 */
export function schemaToBuilderModel(schema: unknown): BuilderModel | null {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) {
    return null;
  }
  const raw = schema as Record<string, unknown>;
  const properties = (raw.properties ?? {}) as Record<string, RawProperty>;
  if (typeof properties !== "object" || Array.isArray(properties)) return null;

  const required = new Set(
    Array.isArray(raw.required)
      ? (raw.required as unknown[]).filter(
          (r): r is string => typeof r === "string"
        )
      : []
  );

  const fields: BuilderField[] = [];
  for (const [key, prop] of Object.entries(properties)) {
    const field = propertyToField(key, prop);
    if (!field) return null;
    field.required = required.has(key);
    fields.push(field);
  }

  const containers: BuilderContainer[] = [];
  if (raw.containers !== undefined) {
    if (!Array.isArray(raw.containers)) return null;
    for (const c of raw.containers) {
      const container = parseContainer(c);
      if (!container) return null;
      containers.push(container);
    }
  }

  return { fields, containers };
}

// ---------------------------------------------------------------------------
// Model -> Schema
// ---------------------------------------------------------------------------

function cleanRows(field: BuilderField): BuilderRow[] {
  switch (field.type) {
    case "ports":
      return field.defaultRows
        .filter(
          (r) => Number(r.local_port) > 0 && Number(r.container_port) > 0
        )
        .map((r) => ({
          local_port: Number(r.local_port),
          container_port: Number(r.container_port),
          protocol: String(r.protocol || "tcp"),
        }));
    case "volumes":
      return field.defaultRows
        .filter((r) => String(r.host_path || "") || String(r.container_path || ""))
        .map((r) => ({
          host_path: String(r.host_path || ""),
          container_path: String(r.container_path || ""),
          mode: String(r.mode || "rw"),
        }));
    case "env":
      return field.defaultRows
        .filter((r) => String(r.key || "").trim())
        .map((r) => ({
          key: String(r.key || ""),
          value: String(r.value ?? ""),
        }));
    case "devices":
      return field.defaultRows
        .filter((r) => String(r.host_path || "").trim())
        .map((r) => ({
          host_path: String(r.host_path || ""),
          container_path: String(r.container_path || ""),
        }));
    default:
      return [];
  }
}

function fieldToProperty(field: BuilderField): Record<string, unknown> {
  const prop: Record<string, unknown> = {};
  if (field.title.trim()) prop.title = field.title.trim();
  if (field.description.trim()) prop.description = field.description.trim();

  switch (field.type) {
    case "string":
      prop.type = "string";
      if (field.defaultValue) prop.default = field.defaultValue;
      break;
    case "password":
      prop.type = "string";
      prop.format = "password";
      if (field.defaultValue) prop.default = field.defaultValue;
      break;
    case "directory":
      prop.type = "string";
      prop.format = "directory";
      if (field.defaultValue) prop.default = field.defaultValue;
      break;
    case "enum": {
      prop.type = "string";
      prop.enum = field.enumOptions.map((o) => o.trim()).filter(Boolean);
      if (field.defaultValue) prop.default = field.defaultValue;
      break;
    }
    case "integer":
    case "number": {
      prop.type = field.type;
      if (field.defaultValue.trim() !== "") {
        const n = Number(field.defaultValue);
        if (!Number.isNaN(n)) prop.default = n;
      }
      if (field.minimum.trim() !== "") {
        const n = Number(field.minimum);
        if (!Number.isNaN(n)) prop.minimum = n;
      }
      if (field.maximum.trim() !== "") {
        const n = Number(field.maximum);
        if (!Number.isNaN(n)) prop.maximum = n;
      }
      break;
    }
    case "boolean":
      prop.type = "boolean";
      prop.default = field.defaultBool;
      break;
    default:
      // 数组类型
      prop.type = "array";
      prop.items = itemsForType(field.type);
      prop.default = cleanRows(field);
      break;
  }
  return prop;
}

/** 将可视化模型序列化为 config_schema JSON 对象 */
export function builderModelToSchema(
  model: BuilderModel
): Record<string, unknown> {
  const properties: Record<string, unknown> = {};
  const required: string[] = [];

  for (const field of model.fields) {
    const key = field.key.trim();
    if (!key) continue;
    properties[key] = fieldToProperty(field);
    if (field.required) required.push(key);
  }

  const schema: Record<string, unknown> = { type: "object", properties };
  if (required.length > 0) schema.required = required;

  const containers = model.containers
    .filter((c) => c.name.trim())
    .map((c) => {
      const settings = SETTING_TYPES.map((st) => ({
        type: st,
        title: SETTING_TITLES[st],
        fields: c.assignments[st].filter((k) => properties[k]),
      })).filter((s) => s.fields.length > 0);
      const container: Record<string, unknown> = {
        name: c.name.trim(),
        title: c.title.trim() || c.name.trim(),
        settings,
      };
      if (c.description.trim()) container.description = c.description.trim();
      return container;
    });
  if (containers.length > 0) schema.containers = containers;

  return schema;
}

/** 创建空字段 */
export function emptyField(type: BuilderFieldType = "string"): BuilderField {
  return {
    key: ARRAY_TYPE_SUGGESTED_KEY[type] ?? "",
    type,
    title: "",
    description: "",
    required: false,
    defaultValue: "",
    defaultBool: false,
    enumOptions: [],
    minimum: "",
    maximum: "",
    defaultRows: [],
  };
}

/** 创建空容器分组 */
export function emptyContainer(name = ""): BuilderContainer {
  return {
    name,
    title: "",
    description: "",
    assignments: { ports: [], volumes: [], env: [], devices: [], advanced: [] },
  };
}

// ---------------------------------------------------------------------------
// YAML 模板生成
// ---------------------------------------------------------------------------

interface ServiceSpec {
  name: string;
  isMain: boolean;
  ports: string[];
  volumes: string[];
  env: string[];
  devices: string[];
  /** advanced 中名为 privileged 的布尔字段 */
  privileged: boolean;
  /** 其他标量字段（仅注释提示，不自动接线） */
  scalars: string[];
  /** 与服务内已有同类型块冲突的字段 */
  conflicts: string[];
}

interface ClassifiedField {
  key: string;
  type: BuilderFieldType;
}

/**
 * 根据 config_schema 生成 Jinja2 Compose YAML 模板。
 * 端口/挂载/环境变量/设备映射数组自动生成循环块，
 * 标量字段以注释形式列出供手动引用。
 */
export function generateYamlTemplate(
  schema: unknown,
  opts: { appName?: string; hasImage?: boolean } = {}
): string {
  const raw = (schema && typeof schema === "object" ? schema : {}) as Record<
    string,
    unknown
  >;
  const properties = (raw.properties ?? {}) as Record<string, RawProperty>;

  const classified: ClassifiedField[] = [];
  for (const [key, prop] of Object.entries(properties)) {
    const type = classifyProperty(prop);
    if (type) classified.push({ key, type });
  }
  const byKey = new Map(classified.map((f) => [f.key, f]));

  // 构建服务列表：有 containers 分组则一容器一服务，否则单服务
  const rawContainers = Array.isArray(raw.containers) ? raw.containers : [];
  const services: ServiceSpec[] = [];

  const newService = (name: string, isMain: boolean): ServiceSpec => ({
    name,
    isMain,
    ports: [],
    volumes: [],
    env: [],
    devices: [],
    privileged: false,
    scalars: [],
    conflicts: [],
  });

  if (rawContainers.length > 0) {
    const assigned = new Set<string>();
    rawContainers.forEach((c, index) => {
      const container = parseContainer(c);
      if (!container) return;
      const service = newService(container.name, index === 0);
      for (const st of SETTING_TYPES) {
        for (const key of container.assignments[st]) {
          const field = byKey.get(key);
          if (!field) continue;
          assigned.add(key);
          assignToService(service, field);
        }
      }
      services.push(service);
    });
    // 未分配字段：数组类型标记到主服务冲突清单，标量列入主服务注释
    for (const field of classified) {
      if (assigned.has(field.key)) continue;
      const main = services[0];
      if (isArrayFieldType(field.type)) {
        main.conflicts.push(`${field.key}（未分配到容器，请手动接入）`);
      } else {
        main.scalars.push(field.key);
      }
    }
  } else {
    const name = opts.appName?.trim() || "app";
    const service = newService(name, true);
    for (const field of classified) assignToService(service, field);
    services.push(service);
  }

  const hasImage = opts.hasImage ?? false;
  const multi = services.length > 1;

  const lines: string[] = [];
  lines.push("# 此模板由可视化配置生成，可按需手动调整。");
  lines.push(
    "# 内置变量: project_name, app_name, image, host_mount_base, container_mount_base"
  );
  const allScalars = services.flatMap((s) => s.scalars);
  if (allScalars.length > 0) {
    // 用 raw 块包裹，避免注释中的 {{ }} 被 Jinja 当作变量渲染
    lines.push(
      `{% raw %}# 标量字段（可用 {{ 字段名 }} 引用）: ${allScalars.join(", ")}{% endraw %}`
    );
  }
  lines.push("services:");
  for (const service of services) {
    lines.push(...renderService(service, { hasImage, multi }));
  }
  return lines.join("\n");
}

function assignToService(service: ServiceSpec, field: ClassifiedField): void {
  switch (field.type) {
    case "ports":
    case "volumes":
    case "env":
    case "devices": {
      const bucket = service[field.type];
      if (bucket.length > 0) {
        service.conflicts.push(
          `${field.key}（与 ${bucket[0]} 同为${SETTING_TITLES[field.type]}，请手动合并）`
        );
      } else {
        bucket.push(field.key);
      }
      break;
    }
    default:
      if (field.type === "boolean" && field.key === "privileged") {
        service.privileged = true;
      } else {
        service.scalars.push(field.key);
      }
      break;
  }
}

function renderService(
  service: ServiceSpec,
  opts: { hasImage: boolean; multi: boolean }
): string[] {
  const lines: string[] = [];
  lines.push(`  ${service.name}:`);
  if (service.isMain && opts.hasImage) {
    lines.push(`    image: {{ image }}`);
  } else {
    lines.push(`    image: ${service.name}:latest  # TODO: 填写镜像`);
  }
  const suffix = opts.multi ? `_${service.name}` : "";
  lines.push(`    container_name: {{ project_name }}${suffix}`);
  lines.push(`    restart: unless-stopped`);
  if (service.privileged) {
    lines.push(`    privileged: {{ privileged | lower }}`);
  }

  for (const key of service.ports) {
    lines.push(
      `{%- if ${key} %}`,
      `    ports:`,
      `{%- for port in ${key} %}`,
      `      - "{{ port.local_port }}:{{ port.container_port }}/{{ port.protocol }}"`,
      `{%- endfor %}`,
      `{%- endif %}`
    );
  }
  for (const key of service.volumes) {
    lines.push(
      `{%- if ${key} %}`,
      `    volumes:`,
      `{%- for vol in ${key} %}`,
      `      - {{ to_host_path(vol.host_path) }}:{{ vol.container_path or to_container_path(vol.host_path) }}:{{ vol.mode }}`,
      `{%- endfor %}`,
      `{%- endif %}`
    );
  }
  for (const key of service.devices) {
    lines.push(
      `{%- if ${key} %}`,
      `    devices:`,
      `{%- for dev in ${key} %}`,
      `      - {{ dev.host_path }}:{{ dev.container_path }}`,
      `{%- endfor %}`,
      `{%- endif %}`
    );
  }
  for (const key of service.env) {
    lines.push(
      `{%- if ${key} %}`,
      `    environment:`,
      `{%- for item in ${key} %}`,
      `      - {{ item.key }}={{ item.value }}`,
      `{%- endfor %}`,
      `{%- endif %}`
    );
  }
  for (const note of service.conflicts) {
    lines.push(`    # TODO: 字段 ${note}`);
  }
  return lines;
}
