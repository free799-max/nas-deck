/**
 * 看板页面组件 - Weihu 风格 Kanban Board
 *
 * 展示四列看板：Todo list / In Progress / In Review / Done
 */

import { useState } from "react";
import { Plus } from "lucide-react";
import { initialColumns, teamMembers } from "./components/mock-data";
import type { Column } from "./components/mock-data";
import { KanbanColumn } from "./components/KanbanColumn";

export function DashboardPage() {
  const [columns] = useState<Column[]>(initialColumns);

  return (
    <div className="space-y-5">
      {/* 页面标题区 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">看板</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            任务进度追踪
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* 成员头像组 */}
          <div className="flex -space-x-2">
            {teamMembers.map((member, i) => (
              <div
                key={i}
                className={`h-7 w-7 rounded-full border-2 border-background flex items-center justify-center text-[9px] font-medium text-foreground ${member.color}`}
              >
                {member.initials}
              </div>
            ))}
          </div>

          {/* Filters 按钮 */}
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-card border border-border/60 text-sm font-medium text-foreground hover:bg-muted transition-colors">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="4" y1="6" x2="20" y2="6" />
              <line x1="4" y1="12" x2="16" y2="12" />
              <line x1="4" y1="18" x2="12" y2="18" />
            </svg>
            筛选
          </button>

          {/* Create task 按钮 */}
          <button className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
            <Plus className="h-3.5 w-3.5" />
            新建任务
          </button>
        </div>
      </div>

      {/* 看板区域 */}
      <div className="flex gap-5 overflow-x-auto pb-4">
        {columns.map((column) => (
          <KanbanColumn key={column.id} column={column} />
        ))}
      </div>
    </div>
  );
}
