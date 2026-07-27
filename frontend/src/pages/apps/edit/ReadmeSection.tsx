/**
 * 应用编辑页 - 文档区块
 *
 * README（Markdown）与更新日志。
 */

import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import type { AppFormState } from "./form-types";

interface ReadmeSectionProps {
  form: AppFormState;
  onChange: (patch: Partial<AppFormState>) => void;
}

export function ReadmeSection({ form, onChange }: ReadmeSectionProps) {
  return (
    <Card className="rounded-xl">
      <CardContent className="p-5 space-y-4">
        <h3 className="text-sm font-semibold text-foreground">文档</h3>

        <div className="space-y-1.5">
          <Label htmlFor="app-readme">README（Markdown）</Label>
          <textarea
            id="app-readme"
            value={form.readme}
            onChange={(e) => onChange({ readme: e.target.value })}
            placeholder="# 应用说明&#10;&#10;支持 Markdown 格式"
            rows={8}
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20 font-mono"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="app-changelog">更新日志</Label>
          <textarea
            id="app-changelog"
            value={form.changelog}
            onChange={(e) => onChange({ changelog: e.target.value })}
            placeholder="版本更新记录（可选）"
            rows={4}
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20 font-mono"
          />
        </div>
      </CardContent>
    </Card>
  );
}
