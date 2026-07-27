/**
 * 应用编辑页 - 部署配置区块
 *
 * 镜像、默认端口（结构化行编辑）、备份路径。
 */

import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Plus, Trash2 } from "lucide-react";
import type { AppFormState, PortRow } from "./form-types";

interface DeployConfigSectionProps {
  form: AppFormState;
  onChange: (patch: Partial<AppFormState>) => void;
}

export function DeployConfigSection({
  form,
  onChange,
}: DeployConfigSectionProps) {
  const updatePort = (index: number, patch: Partial<PortRow>) => {
    const next = form.default_ports.map((row, i) =>
      i === index ? { ...row, ...patch } : row
    );
    onChange({ default_ports: next });
  };

  const addPort = () => {
    onChange({
      default_ports: [
        ...form.default_ports,
        { port: 8080, protocol: "tcp", description: "" },
      ],
    });
  };

  const removePort = (index: number) => {
    onChange({
      default_ports: form.default_ports.filter((_, i) => i !== index),
    });
  };

  return (
    <Card className="rounded-xl">
      <CardContent className="p-5 space-y-4">
        <h3 className="text-sm font-semibold text-foreground">部署配置</h3>

        <div className="space-y-1.5">
          <Label htmlFor="app-image">默认镜像</Label>
          <Input
            id="app-image"
            value={form.image}
            onChange={(e) => onChange({ image: e.target.value })}
            placeholder="如 jxxghp/moviepilot-v2"
          />
          <p className="text-xs text-muted-foreground">
            模板中可通过 {"{{ image }}"} 引用
          </p>
        </div>

        {/* 默认端口 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>默认端口</Label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addPort}
              className="rounded-lg h-7 text-xs"
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              添加端口
            </Button>
          </div>

          {form.default_ports.length === 0 ? (
            <p className="text-xs text-muted-foreground">暂无端口配置</p>
          ) : (
            <div className="space-y-2">
              <div className="grid grid-cols-[100px_90px_1fr_32px] gap-2 text-xs text-muted-foreground px-1">
                <span>端口</span>
                <span>协议</span>
                <span>描述</span>
                <span />
              </div>
              {form.default_ports.map((row, index) => (
                <div
                  key={index}
                  className="grid grid-cols-[100px_90px_1fr_32px] gap-2 items-center"
                >
                  <Input
                    type="number"
                    min={1}
                    max={65535}
                    value={row.port}
                    onChange={(e) =>
                      updatePort(index, { port: Number(e.target.value) || 0 })
                    }
                    className="h-8"
                  />
                  <select
                    value={row.protocol}
                    onChange={(e) =>
                      updatePort(index, { protocol: e.target.value })
                    }
                    className="h-8 rounded-lg border border-border bg-white px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
                  >
                    <option value="tcp">tcp</option>
                    <option value="udp">udp</option>
                  </select>
                  <Input
                    value={row.description}
                    onChange={(e) =>
                      updatePort(index, { description: e.target.value })
                    }
                    placeholder="如 Web UI"
                    className="h-8"
                  />
                  <button
                    type="button"
                    onClick={() => removePort(index)}
                    className="h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="app-backup-paths">默认备份路径</Label>
          <textarea
            id="app-backup-paths"
            value={form.backupPathsText}
            onChange={(e) => onChange({ backupPathsText: e.target.value })}
            placeholder={"每行一个路径，如：\n/config\n/data"}
            rows={3}
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20 font-mono"
          />
        </div>
      </CardContent>
    </Card>
  );
}
