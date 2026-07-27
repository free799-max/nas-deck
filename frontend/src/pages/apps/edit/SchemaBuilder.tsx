/**
 * config_schema 可视化构建器
 *
 * 将 JSON Schema 抽象为字段列表 + 容器分组的可视化编辑：
 * 端口映射、挂载目录、环境变量、设备映射等均有结构化行编辑器，
 * 修改后实时序列化回 config_schema JSON。
 */

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
} from "lucide-react";
import {
  ARRAY_ROW_COLUMNS,
  FIXED_FIELD_TYPES,
  FIXED_TYPE_LABELS,
  PRIVILEGED_KEY,
  SCALAR_FIELD_TYPE_OPTIONS,
  SETTING_TITLES,
  SETTING_TYPES,
  emptyContainer,
  emptyField,
  emptyRowForType,
  fieldFitsSetting,
  isArrayFieldType,
  type BuilderContainer,
  type BuilderField,
  type BuilderFieldType,
  type BuilderModel,
  type BuilderSettingType,
} from "./schema-builder";

interface SchemaBuilderProps {
  model: BuilderModel;
  onChange: (model: BuilderModel) => void;
}

const selectClass =
  "h-8 rounded-lg border border-border bg-white px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20";

export function SchemaBuilder({ model, onChange }: SchemaBuilderProps) {
  const updateField = (index: number, patch: Partial<BuilderField>) => {
    const fields = model.fields.map((f, i) =>
      i === index ? { ...f, ...patch } : f
    );
    onChange({ ...model, fields });
  };

  const moveField = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= model.fields.length) return;
    const fields = [...model.fields];
    [fields[index], fields[target]] = [fields[target], fields[index]];
    onChange({ ...model, fields });
  };

  const removeField = (index: number) => {
    const key = model.fields[index].key;
    const fields = model.fields.filter((_, i) => i !== index);
    // 同步移除容器分组中的引用
    const containers = model.containers.map((c) => ({
      ...c,
      assignments: Object.fromEntries(
        SETTING_TYPES.map((st) => [
          st,
          c.assignments[st].filter((k) => k !== key),
        ])
      ) as BuilderContainer["assignments"],
    }));
    onChange({ ...model, fields, containers });
  };

  const addField = (field: BuilderField) => {
    onChange({ ...model, fields: [...model.fields, field] });
  };

  /** 生成不重复的字段名（如 ports 已存在则 ports_2） */
  const uniqueKey = (base: string) => {
    const keys = new Set(model.fields.map((f) => f.key.trim()));
    if (!keys.has(base)) return base;
    let i = 2;
    while (keys.has(`${base}_${i}`)) i++;
    return `${base}_${i}`;
  };

  /** 添加标准组字段（端口/挂载/环境变量/设备映射，类型固定） */
  const addFixedField = (fixed: (typeof FIXED_FIELD_TYPES)[number]) => {
    const field = emptyField(fixed.type);
    field.key = uniqueKey(fixed.suggestedKey);
    field.title = fixed.suggestedTitle;
    addField(field);
  };

  /** 添加特权模式字段（固定的 boolean 字段） */
  const addPrivilegedField = () => {
    const field = emptyField("boolean");
    field.key = PRIVILEGED_KEY;
    field.title = "特权模式";
    addField(field);
  };

  const hasPrivileged = model.fields.some(
    (f) => f.key.trim() === PRIVILEGED_KEY && f.type === "boolean"
  );

  const updateContainer = (
    index: number,
    patch: Partial<BuilderContainer>
  ) => {
    const containers = model.containers.map((c, i) =>
      i === index ? { ...c, ...patch } : c
    );
    onChange({ ...model, containers });
  };

  // 校验提示：空字段名 / 重复字段名
  const keyCounts = new Map<string, number>();
  for (const f of model.fields) {
    const k = f.key.trim();
    if (k) keyCounts.set(k, (keyCounts.get(k) ?? 0) + 1);
  }
  const duplicateKeys = [...keyCounts.entries()]
    .filter(([, n]) => n > 1)
    .map(([k]) => k);
  const hasEmptyKey = model.fields.some((f) => !f.key.trim());

  // 容器分组启用时，未分配的字段不会出现在部署表单中
  const assignedKeys = new Set(
    model.containers.flatMap((c) =>
      SETTING_TYPES.flatMap((st) => c.assignments[st])
    )
  );
  const unassignedKeys =
    model.containers.length > 0
      ? model.fields
          .map((f) => f.key.trim())
          .filter((k) => k && !assignedKeys.has(k))
      : [];

  return (
    <div className="space-y-4">
      {/* 字段列表 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>配置字段</Label>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-lg h-7 text-xs"
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                添加字段
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-36">
              {FIXED_FIELD_TYPES.map((fixed) => (
                <DropdownMenuItem
                  key={fixed.type}
                  onClick={() => addFixedField(fixed)}
                  className="text-xs"
                >
                  {fixed.label}
                </DropdownMenuItem>
              ))}
              <DropdownMenuItem
                onClick={addPrivilegedField}
                disabled={hasPrivileged}
                className="text-xs"
              >
                特权模式
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => addField(emptyField("string"))}
                className="text-xs"
              >
                自定义字段
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {model.fields.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            暂无字段。点击"添加字段"添加端口映射、挂载目录、环境变量等配置项。
          </p>
        ) : (
          <div className="space-y-2">
            {model.fields.map((field, index) => (
              <FieldCard
                key={index}
                field={field}
                onChange={(patch) => updateField(index, patch)}
                onMoveUp={() => moveField(index, -1)}
                onMoveDown={() => moveField(index, 1)}
                onRemove={() => removeField(index)}
                canMoveUp={index > 0}
                canMoveDown={index < model.fields.length - 1}
                keyDuplicate={
                  !!field.key.trim() &&
                  (keyCounts.get(field.key.trim()) ?? 0) > 1
                }
              />
            ))}
          </div>
        )}

        {(hasEmptyKey || duplicateKeys.length > 0) && (
          <div className="flex items-start gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>
              {hasEmptyKey && "存在未命名字段，保存时将被忽略。"}
              {duplicateKeys.length > 0 &&
                `字段名重复：${duplicateKeys.join("、")}`}
            </span>
          </div>
        )}
      </div>

      {/* 容器分组 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <Label>容器分组</Label>
            <p className="text-xs text-muted-foreground mt-0.5">
              多容器应用按容器组织字段（部署向导按组展示）；单容器应用无需启用
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              onChange({
                ...model,
                containers:
                  model.containers.length > 0 ? [] : [emptyContainer("app")],
              })
            }
            className="rounded-lg h-7 text-xs"
          >
            {model.containers.length > 0 ? "取消分组" : "启用分组"}
          </Button>
        </div>

        {model.containers.length > 0 && (
          <div className="space-y-2">
            {model.containers.map((container, index) => (
              <ContainerCard
                key={index}
                container={container}
                fields={model.fields}
                onChange={(patch) => updateContainer(index, patch)}
                onRemove={() =>
                  onChange({
                    ...model,
                    containers: model.containers.filter((_, i) => i !== index),
                  })
                }
              />
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                onChange({
                  ...model,
                  containers: [...model.containers, emptyContainer()],
                })
              }
              className="rounded-lg h-7 text-xs"
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              添加容器
            </Button>

            {unassignedKeys.length > 0 && (
              <div className="flex items-start gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                <span>
                  以下字段未分配到任何容器，部署表单中不会显示：
                  {unassignedKeys.join("、")}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 字段卡片
// ---------------------------------------------------------------------------

interface FieldCardProps {
  field: BuilderField;
  onChange: (patch: Partial<BuilderField>) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onRemove: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
  keyDuplicate: boolean;
}

function FieldCard({
  field,
  onChange,
  onMoveUp,
  onMoveDown,
  onRemove,
  canMoveUp,
  canMoveDown,
  keyDuplicate,
}: FieldCardProps) {
  // 标准组与特权模式为固定类型，展示标识而非类型选择
  const fixedLabel = isArrayFieldType(field.type)
    ? FIXED_TYPE_LABELS[field.type]
    : field.type === "boolean" && field.key.trim() === PRIVILEGED_KEY
      ? "特权模式"
      : null;

  return (
    <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <Input
          value={field.key}
          onChange={(e) => onChange({ key: e.target.value })}
          placeholder="字段名，如 ports"
          className={`h-8 w-44 font-mono text-xs ${keyDuplicate ? "border-destructive" : ""}`}
        />
        {fixedLabel ? (
          <span className="h-8 w-40 inline-flex items-center rounded-lg border border-transparent bg-primary/10 px-2 text-xs font-medium text-primary">
            {fixedLabel}
          </span>
        ) : (
          <select
            value={field.type}
            onChange={(e) =>
              onChange({ type: e.target.value as BuilderFieldType })
            }
            className={`${selectClass} w-40`}
          >
            {SCALAR_FIELD_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        )}
        <Input
          value={field.title}
          onChange={(e) => onChange({ title: e.target.value })}
          placeholder="显示标题，如 端口设置"
          className="h-8 flex-1"
        />
        <label className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
          <input
            type="checkbox"
            checked={field.required}
            onChange={(e) => onChange({ required: e.target.checked })}
            className="h-3.5 w-3.5 rounded border-input"
          />
          必填
        </label>
        <button
          type="button"
          onClick={onMoveUp}
          disabled={!canMoveUp}
          className="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:bg-accent disabled:opacity-30"
          title="上移"
        >
          <ArrowUp className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={onMoveDown}
          disabled={!canMoveDown}
          className="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:bg-accent disabled:opacity-30"
          title="下移"
        >
          <ArrowDown className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={onRemove}
          className="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          title="删除字段"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <Input
        value={field.description}
        onChange={(e) => onChange({ description: e.target.value })}
        placeholder="描述说明（可选，部署表单中显示为提示）"
        className="h-8 text-xs"
      />

      <FieldTypeOptions field={field} onChange={onChange} />
    </div>
  );
}

/** 按字段类型渲染专属配置项 */
function FieldTypeOptions({
  field,
  onChange,
}: {
  field: BuilderField;
  onChange: (patch: Partial<BuilderField>) => void;
}) {
  switch (field.type) {
    case "string":
    case "password":
    case "directory":
      return (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground w-16 shrink-0">
            默认值
          </span>
          <Input
            value={field.defaultValue}
            onChange={(e) => onChange({ defaultValue: e.target.value })}
            placeholder={
              field.type === "directory" ? "如 media/movies" : "默认值（可选）"
            }
            className="h-8 text-xs"
          />
        </div>
      );
    case "integer":
    case "number":
      return (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground w-16 shrink-0">
            默认值
          </span>
          <Input
            type="number"
            value={field.defaultValue}
            onChange={(e) => onChange({ defaultValue: e.target.value })}
            placeholder="默认值"
            className="h-8 text-xs w-28"
          />
          <span className="text-xs text-muted-foreground shrink-0">范围</span>
          <Input
            type="number"
            value={field.minimum}
            onChange={(e) => onChange({ minimum: e.target.value })}
            placeholder="最小"
            className="h-8 text-xs w-24"
          />
          <span className="text-xs text-muted-foreground">-</span>
          <Input
            type="number"
            value={field.maximum}
            onChange={(e) => onChange({ maximum: e.target.value })}
            placeholder="最大"
            className="h-8 text-xs w-24"
          />
        </div>
      );
    case "boolean":
      return (
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={field.defaultBool}
            onChange={(e) => onChange({ defaultBool: e.target.checked })}
            className="h-3.5 w-3.5 rounded border-input"
          />
          默认开启
        </label>
      );
    case "enum":
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground w-16 shrink-0">
              选项
            </span>
            <Input
              value={field.enumOptions.join(", ")}
              onChange={(e) =>
                onChange({
                  enumOptions: e.target.value
                    .split(/[,，]/)
                    .map((s) => s.trim()),
                })
              }
              placeholder="逗号分隔，如 latest, stable, beta"
              className="h-8 text-xs"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground w-16 shrink-0">
              默认值
            </span>
            <Input
              value={field.defaultValue}
              onChange={(e) => onChange({ defaultValue: e.target.value })}
              placeholder="默认值（可选）"
              className="h-8 text-xs w-40"
            />
          </div>
        </div>
      );
    default:
      // 数组类型：默认值行编辑器
      return <ArrayRowsEditor field={field} onChange={onChange} />;
  }
}

// ---------------------------------------------------------------------------
// 数组字段默认值行编辑器
// ---------------------------------------------------------------------------

function ArrayRowsEditor({
  field,
  onChange,
}: {
  field: BuilderField;
  onChange: (patch: Partial<BuilderField>) => void;
}) {
  const columns = ARRAY_ROW_COLUMNS[field.type] ?? [];
  const rows = field.defaultRows;

  const updateRow = (index: number, key: string, value: string | number) => {
    const next = rows.map((r, i) =>
      i === index ? { ...r, [key]: value } : r
    );
    onChange({ defaultRows: next });
  };

  const gridCols =
    columns.length === 3
      ? "grid-cols-[1fr_1fr_90px_32px]"
      : "grid-cols-[1fr_1fr_32px]";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          默认值（部署时用户可增删改）
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            onChange({
              defaultRows: [...rows, emptyRowForType(field.type)],
            })
          }
          className="rounded-lg h-6 text-xs px-2"
        >
          <Plus className="h-3 w-3 mr-1" />
          添加行
        </Button>
      </div>

      {rows.length > 0 && (
        <div className="space-y-1.5">
          <div
            className={`grid ${gridCols} gap-2 text-xs text-muted-foreground px-0.5`}
          >
            {columns.map((c) => (
              <span key={c.key}>{c.label}</span>
            ))}
            <span />
          </div>
          {rows.map((row, index) => (
            <div
              key={index}
              className={`grid ${gridCols} gap-2 items-center`}
            >
              {columns.map((col) => {
                if (col.input === "select") {
                  return (
                    <select
                      key={col.key}
                      value={String(row[col.key] ?? col.options?.[0] ?? "")}
                      onChange={(e) => updateRow(index, col.key, e.target.value)}
                      className={selectClass}
                    >
                      {col.options?.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  );
                }
                if (col.input === "number") {
                  const n = Number(row[col.key] ?? 0);
                  return (
                    <Input
                      key={col.key}
                      type="number"
                      value={n === 0 ? "" : n}
                      onChange={(e) =>
                        updateRow(index, col.key, Number(e.target.value) || 0)
                      }
                      placeholder={col.label}
                      className="h-8 text-xs"
                    />
                  );
                }
                return (
                  <Input
                    key={col.key}
                    value={String(row[col.key] ?? "")}
                    onChange={(e) => updateRow(index, col.key, e.target.value)}
                    placeholder={col.label}
                    className="h-8 text-xs"
                  />
                );
              })}
              <button
                type="button"
                onClick={() =>
                  onChange({
                    defaultRows: rows.filter((_, i) => i !== index),
                  })
                }
                className="h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 容器分组卡片
// ---------------------------------------------------------------------------

function ContainerCard({
  container,
  fields,
  onChange,
  onRemove,
}: {
  container: BuilderContainer;
  fields: BuilderField[];
  onChange: (patch: Partial<BuilderContainer>) => void;
  onRemove: () => void;
}) {
  const toggleAssignment = (settingType: BuilderSettingType, key: string) => {
    const current = container.assignments[settingType];
    const next = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key];
    onChange({
      assignments: { ...container.assignments, [settingType]: next },
    });
  };

  const validFields = fields.filter((f) => f.key.trim());

  return (
    <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <Input
          value={container.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="容器标识，如 app / redis"
          className="h-8 w-44 font-mono text-xs"
        />
        <Input
          value={container.title}
          onChange={(e) => onChange({ title: e.target.value })}
          placeholder="显示标题，如 Redis 缓存"
          className="h-8 flex-1"
        />
        <button
          type="button"
          onClick={onRemove}
          className="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          title="删除容器"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <Input
        value={container.description}
        onChange={(e) => onChange({ description: e.target.value })}
        placeholder="容器描述（可选）"
        className="h-8 text-xs"
      />

      {/* 设置块字段分配 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
        {SETTING_TYPES.map((st) => {
          const eligible = validFields.filter((f) =>
            fieldFitsSetting(f.type, st)
          );
          if (eligible.length === 0) return null;
          return (
            <div key={st} className="space-y-1">
              <span className="text-xs font-medium text-muted-foreground">
                {SETTING_TITLES[st]}
              </span>
              <div className="flex flex-wrap gap-x-3 gap-y-1">
                {eligible.map((f) => (
                  <label
                    key={f.key}
                    className="flex items-center gap-1 text-xs text-foreground"
                  >
                    <input
                      type="checkbox"
                      checked={container.assignments[st].includes(f.key.trim())}
                      onChange={() => toggleAssignment(st, f.key.trim())}
                      className="h-3.5 w-3.5 rounded border-input"
                    />
                    <span className="font-mono">{f.key.trim()}</span>
                  </label>
                ))}
              </div>
            </div>
          );
        })}
        {validFields.length === 0 && (
          <p className="text-xs text-muted-foreground">
            请先添加配置字段，再分配到容器
          </p>
        )}
      </div>
    </div>
  );
}
