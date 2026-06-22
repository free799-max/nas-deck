/**
 * JSON Schema 动态表单组件
 *
 * 支持两种格式：
 * 1. 新格式：按容器分组，schema.containers 定义容器、设置块及字段
 * 2. 旧格式：平铺 properties，按端口/挂载/环境变量/其他自动分组
 */

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Minus, Plus, ChevronUp, ChevronDown } from "lucide-react";

/** Schema 属性定义 */
export interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  items?: {
    type?: string;
    properties?: Record<string, SchemaProperty>;
    required?: string[];
  };
}

/** 容器内设置块 */
export interface ContainerSetting {
  type: "ports" | "volumes" | "env";
  title: string;
  description?: string;
  fields: string[];
}

/** 容器配置 */
export interface ContainerConfig {
  name: string;
  title: string;
  description?: string;
  settings: ContainerSetting[];
}

interface SchemaFormProps {
  /** JSON Schema */
  schema: {
    properties?: Record<string, SchemaProperty>;
    required?: string[];
    containers?: ContainerConfig[];
  };
  /** 当前表单数据 */
  data: Record<string, unknown>;
  /** 表单数据变化回调 */
  onChange: (data: Record<string, unknown>) => void;
}

/** 字段分组标识（旧格式用） */
export type FieldGroup = "ports" | "mounts" | "env" | "others";

/** 旧格式分组配置 */
const GROUP_CONFIG: Record<FieldGroup, { label: string }> = {
  ports: { label: "端口" },
  mounts: { label: "挂载目录" },
  env: { label: "环境变量" },
  others: { label: "其他" },
};

const GROUP_ORDER: FieldGroup[] = ["ports", "mounts", "env", "others"];

/**
 * 根据字段 key 和 title 判断所属分组（旧格式用）。
 * 优先级：端口 > 挂载目录 > 环境变量 > 其他
 */
function getGroup(key: string, prop: SchemaProperty): FieldGroup {
  const k = key.toLowerCase();
  const t = (prop.title || "").toLowerCase();

  const isPort = k.includes("port") || t.includes("端口");

  const isMount =
    k.includes("path") ||
    k.includes("dir") ||
    t.includes("路径") ||
    t.includes("目录");

  const isKeyLike =
    k.includes("api_key") ||
    k.includes("secret_key") ||
    k.includes("access_key") ||
    k.includes("private_key") ||
    k.endsWith("_key");

  const isEnv =
    k.includes("user") ||
    k.includes("username") ||
    k.includes("password") ||
    k.includes("pass") ||
    k.includes("token") ||
    k.includes("secret") ||
    isKeyLike ||
    k.includes("umask") ||
    k.includes("timezone") ||
    k === "tz" ||
    k.includes("env_") ||
    k.endsWith("_env") ||
    t.includes("密码") ||
    t.includes("账号") ||
    t.includes("用户名") ||
    t.includes("用户") ||
    t.includes("密钥") ||
    t.includes("令牌") ||
    t.includes("时区");

  if (isPort) return "ports";
  if (isMount) return "mounts";
  if (isEnv) return "env";
  return "others";
}

interface FieldInputProps {
  propKey: string;
  prop: SchemaProperty;
  value: unknown;
  required: boolean;
  onChange: (key: string, value: unknown) => void;
  hideLabel?: boolean;
}

function FieldInput({
  propKey,
  prop,
  value,
  required,
  onChange,
  hideLabel = false,
}: FieldInputProps) {
  const label = prop.title || propKey;

  const handleChange = (next: unknown) => {
    onChange(propKey, next);
  };

  const labelNode = (
    <Label
      htmlFor={propKey}
      className="text-xs font-medium"
      aria-required={required}
      title={required ? "必填" : undefined}
    >
      {label}
      {required && (
        <span className="ml-0.5 text-destructive" aria-hidden="true">
          *
        </span>
      )}
    </Label>
  );

  if (prop.type === "boolean") {
    return (
      <div className="flex items-center gap-2">
        <input
          id={propKey}
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => handleChange(e.target.checked)}
          className="h-4 w-4 rounded border-input"
        />
        {labelNode}
      </div>
    );
  }

  if (prop.enum && prop.enum.length > 0) {
    return (
      <div className="space-y-1">
        {!hideLabel && labelNode}
        <select
          id={propKey}
          value={String(value ?? "")}
          onChange={(e) => handleChange(e.target.value)}
          className="flex h-8 w-full rounded-md border border-input bg-white px-2 py-1 text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          {prop.enum.map((option) => (
            <option key={String(option)} value={String(option)}>
              {String(option)}
            </option>
          ))}
        </select>
      </div>
    );
  }

  const inputType =
    prop.type === "integer" || prop.type === "number" ? "number" : "text";

  return (
    <div className="space-y-1">
      {!hideLabel && labelNode}
      <Input
        id={propKey}
        type={inputType}
        value={value === undefined || value === null ? "" : String(value)}
        onChange={(e) => {
          const raw = e.target.value;
          if (prop.type === "integer") {
            handleChange(raw === "" ? "" : parseInt(raw, 10));
          } else if (prop.type === "number") {
            handleChange(raw === "" ? "" : parseFloat(raw));
          } else {
            handleChange(raw);
          }
        }}
        placeholder={hideLabel ? label : prop.description}
        className="h-8 rounded-md border-input bg-white px-2 text-sm shadow-none"
      />
    </div>
  );
}

interface ArrayFieldProps {
  propKey: string;
  prop: SchemaProperty;
  value: unknown;
  required: boolean;
  onChange: (key: string, value: unknown) => void;
  settingType: string;
}

function ArrayField({
  propKey,
  prop,
  value,
  required,
  onChange,
  settingType,
}: ArrayFieldProps) {
  const rows = Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
  const items = prop.items || {};
  const itemProps = items.properties || {};
  const itemRequired = new Set(items.required || []);

  const defaultRow = (): Record<string, unknown> => {
    const row: Record<string, unknown> = {};
    for (const [key, p] of Object.entries(itemProps)) {
      if (p && "default" in p) {
        row[key] = p.default;
      } else if (itemRequired.has(key)) {
        row[key] = "";
      }
    }
    return row;
  };

  const updateRows = (newRows: Record<string, unknown>[]) => {
    onChange(propKey, newRows);
  };

  const addRow = () => {
    updateRows([...rows, defaultRow()]);
  };

  const removeRow = (index: number) => {
    const newRows = rows.filter((_, i) => i !== index);
    updateRows(newRows);
  };

  const updateRow = (index: number, key: string, val: unknown) => {
    const newRows = rows.map((row, i) =>
      i === index ? { ...row, [key]: val } : row
    );
    updateRows(newRows);
  };

  const gridCols =
    settingType === "ports"
      ? "grid-cols-[1fr_1fr_80px_32px]"
      : "grid-cols-[1fr_1fr_90px_32px]";

  return (
    <div className="space-y-1.5">
      {rows.map((row, index) => (
        <div key={index} className={`grid ${gridCols} gap-2 items-end`}>
          {Object.entries(itemProps).map(([key, p]) => (
            <FieldInput
              key={key}
              propKey={key}
              prop={p}
              value={row[key]}
              required={itemRequired.has(key)}
              onChange={(_, val) => updateRow(index, key, val)}
              hideLabel
            />
          ))}
          <Button
            type="button"
            variant="secondary"
            size="icon"
            className="h-8 w-8 rounded-sm"
            onClick={() => removeRow(index)}
            disabled={required && rows.length <= 1}
          >
            <Minus className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="h-8 gap-1 rounded-md"
        onClick={addRow}
      >
        <Plus className="h-4 w-4" />
        新增
      </Button>
    </div>
  );
}

/** 旧格式渲染 */
function LegacySchemaForm({
  schema,
  data,
  onChange,
}: {
  schema: SchemaFormProps["schema"];
  data: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
}) {
  const properties = schema.properties || {};
  const requiredSet = new Set(schema.required || []);
  const [expanded, setExpanded] = useState<Set<FieldGroup>>(
    new Set(GROUP_ORDER)
  );

  const toggleGroup = (groupKey: FieldGroup) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(groupKey)) next.delete(groupKey);
      else next.add(groupKey);
      return next;
    });
  };

  const handleChange = (key: string, value: unknown) => {
    onChange({ ...data, [key]: value });
  };

  const groups = new Map<FieldGroup, [string, SchemaProperty][]>();

  for (const [key, prop] of Object.entries(properties)) {
    const group = getGroup(key, prop);
    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group)!.push([key, prop]);
  }

  return (
    <div className="divide-y rounded-lg border bg-card p-4 shadow-sm">
      {GROUP_ORDER.map((groupKey) => {
        const fields = groups.get(groupKey);
        if (!fields || fields.length === 0) return null;

        const config = GROUP_CONFIG[groupKey];
        const isPorts = groupKey === "ports";
        const isExpanded = expanded.has(groupKey);

        return (
          <section key={groupKey} className="py-3 first:pt-0 last:pb-0">
            <button
              type="button"
              onClick={() => toggleGroup(groupKey)}
              className="flex items-center gap-1.5 text-left group"
            >
              {isExpanded ? (
                <ChevronUp className="h-3.5 w-3.5 text-primary transition-transform" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5 text-primary transition-transform" />
              )}
              <h4 className="text-xs font-semibold text-primary group-hover:underline">
                {config.label}
              </h4>
            </button>
            {isExpanded && (
              <div
                className={
                  isPorts
                    ? "mt-2 grid grid-cols-2 gap-3"
                    : "mt-2 grid grid-cols-1 gap-3"
                }
              >
                {fields.map(([key, prop]) => (
                  <FieldInput
                    key={key}
                    propKey={key}
                    prop={prop}
                    value={data[key]}
                    required={requiredSet.has(key)}
                    onChange={handleChange}
                  />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

/** 新格式：按容器分组渲染 */
function ContainerSchemaForm({
  schema,
  data,
  onChange,
}: {
  schema: SchemaFormProps["schema"];
  data: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
}) {
  const properties = schema.properties || {};
  const requiredSet = new Set(schema.required || []);
  const containers = schema.containers || [];

  const allKeys = containers.flatMap((container) =>
    container.settings.map((setting) => `${container.name}-${setting.type}`)
  );
  const [expanded, setExpanded] = useState<Set<string>>(new Set(allKeys));

  const toggleSection = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleChange = (key: string, value: unknown) => {
    onChange({ ...data, [key]: value });
  };

  const renderFields = (fields: string[], settingType: string) => {
    return (
      <div className="space-y-2">
        {fields
          .filter((key) => properties[key])
          .map((key) => {
            const prop = properties[key];
            if (prop.type === "array" && prop.items) {
              return (
                <ArrayField
                  key={key}
                  propKey={key}
                  prop={prop}
                  value={data[key]}
                  required={requiredSet.has(key)}
                  onChange={handleChange}
                  settingType={settingType}
                />
              );
            }
            return (
              <FieldInput
                key={key}
                propKey={key}
                prop={prop}
                value={data[key]}
                required={requiredSet.has(key)}
                onChange={handleChange}
                hideLabel
              />
            );
          })}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {containers.map((container) => (
        <section
          key={container.name}
          className="rounded-xl border bg-card p-4 shadow-sm"
        >
          <div className="mb-3">
            <h3 className="text-sm font-semibold text-card-foreground">
              {container.title}
            </h3>
            {container.description && (
              <p className="text-xs text-muted-foreground leading-snug">
                {container.description}
              </p>
            )}
          </div>

          <div className="divide-y">
            {container.settings
              .filter(
                (setting) =>
                  setting.fields &&
                  setting.fields.some((key) => properties[key])
              )
              .map((setting) => {
                const sectionKey = `${container.name}-${setting.type}`;
                const isExpanded = expanded.has(sectionKey);
                return (
                  <div
                    key={sectionKey}
                    className="py-3 first:pt-0 last:pb-0"
                  >
                    <button
                      type="button"
                      onClick={() => toggleSection(sectionKey)}
                      className="flex items-center gap-1.5 text-left group"
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-3.5 w-3.5 text-primary transition-transform" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5 text-primary transition-transform" />
                      )}
                      <h4 className="text-xs font-semibold text-primary group-hover:underline">
                        {setting.title}
                      </h4>
                    </button>
                    {isExpanded && (
                      <div className="mt-2">
                        {setting.description && (
                          <p className="mb-2 text-xs text-muted-foreground leading-snug">
                            {setting.description}
                          </p>
                        )}
                        {renderFields(setting.fields, setting.type)}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        </section>
      ))}
    </div>
  );
}

export function SchemaForm({ schema, data, onChange }: SchemaFormProps) {
  if (schema.containers && schema.containers.length > 0) {
    return (
      <ContainerSchemaForm schema={schema} data={data} onChange={onChange} />
    );
  }

  return <LegacySchemaForm schema={schema} data={data} onChange={onChange} />;
}
