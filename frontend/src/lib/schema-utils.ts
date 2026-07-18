/**
 * JSON Schema 表单工具函数
 *
 * 用于从 Schema 提取默认值、为密码字段自动生成密码等。
 */

import { generatePassword } from "@/lib/utils";

/** 带 items 的 Schema 属性定义 */
export interface SchemaPropertyWithItems extends Record<string, unknown> {
  format?: string;
  type?: string;
  items?: {
    properties?: Record<string, SchemaPropertyWithItems>;
  };
  default?: unknown;
}

/**
 * 从 JSON Schema 中提取默认值。
 *
 * - 有 default 的字段使用 default 值
 * - required 且无 default 的字段用空字符串占位，避免 schema 校验立即失败
 */
export function extractDefaults(
  schema: Record<string, unknown>
): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  const properties = schema?.properties as
    | Record<string, { default?: unknown }>
    | undefined;
  const required = new Set((schema?.required as string[] | undefined) || []);
  if (properties) {
    for (const [key, prop] of Object.entries(properties)) {
      if (prop && "default" in prop) {
        defaults[key] = prop.default;
      } else if (required.has(key)) {
        defaults[key] = "";
      }
    }
  }
  return defaults;
}

/**
 * 遍历 defaults，为空密码字段自动生成密码。
 *
 * 包括：format === "password" 的字段，以及 key/value 数组中 key 包含
 * password/pass 且 value 为空的项。
 */
export function fillEmptyPasswords(
  schema: Record<string, unknown>,
  defaults: Record<string, unknown>
): Record<string, unknown> {
  const properties = schema?.properties as
    | Record<string, SchemaPropertyWithItems>
    | undefined;
  if (!properties) return defaults;

  const filled = structuredClone(defaults);

  for (const [key, prop] of Object.entries(properties)) {
    if (prop.format === "password") {
      const value = filled[key];
      if (value === "" || value === undefined || value === null) {
        filled[key] = generatePassword();
      }
      continue;
    }

    if (
      prop.type === "array" &&
      prop.items?.properties &&
      "key" in prop.items.properties &&
      "value" in prop.items.properties
    ) {
      const rows = Array.isArray(filled[key])
        ? (filled[key] as Record<string, unknown>[])
        : [];
      filled[key] = rows.map((row) => {
        const keyValue = String(row?.key || "").toLowerCase();
        const value = row?.value;
        if (
          (keyValue.includes("password") || keyValue.includes("pass")) &&
          (value === "" || value === undefined || value === null)
        ) {
          return { ...row, value: generatePassword() };
        }
        return row;
      });
    }
  }

  return filled;
}
