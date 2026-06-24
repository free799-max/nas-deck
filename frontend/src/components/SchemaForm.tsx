/**
 * JSON Schema 动态表单组件
 *
 * 按容器分组渲染：schema.containers 定义容器、设置块及字段。
 */

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { DirectoryPicker } from "@/components/DirectoryPicker";
import { generatePassword } from "@/lib/utils";
import { useSystemConfig } from "@/hooks/useSettings";
import { Minus, Plus, ChevronUp, ChevronDown, FolderOpen, RefreshCw } from "lucide-react";

/** Schema 属性定义 */
export interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  format?: string;
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
  const [pickerOpen, setPickerOpen] = useState(false);
  const { data: systemConfig } = useSystemConfig();

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

  const isPasswordField = prop.format === "password";
  const isDirectoryField = prop.format === "directory";

  const inputType =
    prop.type === "integer" || prop.type === "number" ? "number" : "text";

  const inputNode = (
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
  );

  // 目录选择：输入框 + 浏览按钮
  if (isDirectoryField) {
    const dockerMountDir = systemConfig?.storage_docker_mount_dir;
    const currentValue = value === undefined || value === null ? "" : String(value);
    const pickerInitialPath =
      currentValue && currentValue.startsWith("/")
        ? currentValue
        : dockerMountDir || "/";

    return (
      <div className="space-y-1">
        {!hideLabel && labelNode}
        <div className="flex items-center gap-2">
          {inputNode}
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
        <DirectoryPicker
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          initialPath={pickerInitialPath}
          onSelect={(path) => handleChange(path)}
        />
      </div>
    );
  }

  // 密码生成：输入框 + 生成按钮（默认明文显示）
  if (isPasswordField) {
    return (
      <div className="space-y-1">
        {!hideLabel && labelNode}
        <div className="flex items-center gap-2">
          {inputNode}
          <Button
            type="button"
            variant="secondary"
            size="icon"
            className="h-8 w-8 shrink-0 rounded-md"
            onClick={() => handleChange(generatePassword())}
            title="重新生成密码"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {!hideLabel && labelNode}
      {inputNode}
    </div>
  );
}

interface ArrayFieldProps {
  propKey: string;
  prop: SchemaProperty;
  value: unknown;
  required: boolean;
  onChange: (key: string, value: unknown) => void;
}

function ArrayField({
  propKey,
  prop,
  value,
  required,
  onChange,
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

  const addRow = (index: number) => {
    const newRows = [...rows];
    newRows.splice(index + 1, 0, defaultRow());
    updateRows(newRows);
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

  const itemPropEntries = Object.entries(itemProps);
  const isTwoColumnRow = itemPropEntries.length === 2;

  // 使用 display: contents 让每行子元素直接参与外层统一 grid：
  // grid-cols-[1fr_1fr_90px_auto]
  // - 3 个字段（ports/volumes）：各占 1 列，按钮在第 4 列
  // - 2 个字段（env）：key 占 1 列，value 跨 2-3 列，按钮在第 4 列，不留空白
  return (
    <>
      {rows.map((row, index) => (
        <div key={`${propKey}-row-${index}`} className="contents">
          {itemPropEntries.map(([key, p]) => {
            // key/value 数组中，根据 key 的值推断 value 的语义
            let prop = p;
            if (
              key === "value" &&
              "key" in itemProps &&
              row.key !== undefined
            ) {
              const keyValue = String(row.key).toLowerCase();
              if (keyValue.includes("password") || keyValue.includes("pass")) {
                prop = { ...p, format: "password" };
              }
            }
            const colSpan =
              isTwoColumnRow && key === "value" ? "col-span-2" : "col-span-1";
            return (
              <div key={key} className={colSpan}>
                <FieldInput
                  propKey={key}
                  prop={prop}
                  value={row[key]}
                  required={itemRequired.has(key)}
                  onChange={(_, val) => updateRow(index, key, val)}
                  hideLabel
                />
              </div>
            );
          })}
          <div className="col-span-1 flex items-center justify-end gap-2 mr-2">
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
            <Button
              type="button"
              variant="secondary"
              size="icon"
              className="h-8 w-8 rounded-sm"
              onClick={() => addRow(index)}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ))}
      {rows.length === 0 && (
        <div className="contents">
          <div className="col-span-4">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="h-8 gap-1 rounded-md mr-2"
              onClick={() => addRow(0)}
            >
              <Plus className="h-4 w-4" />
              新增
            </Button>
          </div>
        </div>
      )}
    </>
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

  const renderFields = (fields: string[]) => {
    // 端口/存储空间：3 字段，协议/权限列占 90px，按钮在 auto 列
    // 环境变量：2 字段，按钮直接放 auto 列，由相同按钮组自然对齐，不留空白列
    const gridClass = "grid-cols-[1fr_1fr_90px_auto]";
    return (
      <div className={`grid ${gridClass} gap-2`}>
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
                />
              );
            }
            return (
              <div key={key} className="col-span-4">
                <FieldInput
                  propKey={key}
                  prop={prop}
                  value={data[key]}
                  required={requiredSet.has(key)}
                  onChange={handleChange}
                  hideLabel
                />
              </div>
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
                        {renderFields(setting.fields)}
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
  return (
    <ContainerSchemaForm schema={schema} data={data} onChange={onChange} />
  );
}
