/**
 * 看板列组件
 *
 * 单列看板，包含列标题和任务卡片列表。
 */

import { Plus, MoreHorizontal } from "lucide-react";
import type { Column } from "./mock-data";
import { TaskCard } from "./TaskCard";

export function KanbanColumn({ column }: { column: Column }) {
  return (
    <div className="flex-shrink-0 w-[280px]">
      {/* 列标题 */}
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">›</span>
          <h3 className="text-sm font-semibold text-foreground">{column.title}</h3>
        </div>
        <div className="flex items-center gap-0.5">
          <button className="h-6 w-6 rounded-lg hover:bg-white flex items-center justify-center text-muted-foreground transition-colors">
            <Plus className="h-3.5 w-3.5" />
          </button>
          <button className="h-6 w-6 rounded-lg hover:bg-white flex items-center justify-center text-muted-foreground transition-colors">
            <MoreHorizontal className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* 任务列表 */}
      <div className="space-y-3">
        {column.tasks.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </div>
    </div>
  );
}
