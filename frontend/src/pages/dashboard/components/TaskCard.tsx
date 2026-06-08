/**
 * 看板任务卡片组件
 *
 * 展示单个任务的标签、标题、备注、检查清单、进度和底部统计信息。
 */

import { MoreHorizontal, MessageSquare, Paperclip, Check } from "lucide-react";
import type { Task } from "./mock-data";
import { AvatarStack } from "./AvatarStack";
import { ProgressDots } from "./ProgressDots";

export function TaskCard({ task }: { task: Task }) {
  return (
    <div
      className={`rounded-2xl p-4 ${task.bgColor} cursor-pointer hover:shadow-md transition-shadow`}
    >
      {/* 标签 */}
      <div className="flex items-center gap-1.5 flex-wrap mb-2.5">
        {task.tags.map((tag) => (
          <span
            key={tag.label}
            className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium ${tag.color}`}
          >
            {tag.label}
          </span>
        ))}
        <button className="ml-auto text-muted-foreground hover:text-foreground">
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 标题 */}
      <h4 className="text-sm font-semibold text-foreground leading-snug mb-1">
        {task.title}
      </h4>

      {/* 内部占位图（部分卡片有） */}
      {task.id === "p1" && (
        <div className="mt-2 rounded-xl bg-white/70 p-2 space-y-1.5">
          <div className="h-1.5 w-3/4 bg-amber-200/60 rounded-full" />
          <div className="h-1.5 w-1/2 bg-amber-200/40 rounded-full" />
          <div className="flex gap-1.5 mt-1">
            <div className="h-6 flex-1 rounded bg-amber-100/60" />
            <div className="h-6 flex-1 rounded bg-amber-100/40" />
            <div className="h-6 flex-1 rounded bg-amber-100/60" />
          </div>
        </div>
      )}

      {/* Note */}
      {task.note && (
        <p className="text-[11px] text-muted-foreground mt-2">Note: {task.note}</p>
      )}

      {/* Checklist */}
      {task.checklist && (
        <div className="mt-2 space-y-1">
          {task.checklist.map((item, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <div
                className={`h-3.5 w-3.5 rounded-full flex items-center justify-center ${
                  item.done ? "bg-[#7c3aed]" : "border border-gray-300"
                }`}
              >
                {item.done && <Check className="h-2.5 w-2.5 text-white" strokeWidth={3} />}
              </div>
              <span
                className={`text-[11px] ${
                  item.done ? "text-foreground line-through opacity-60" : "text-muted-foreground"
                }`}
              >
                {item.text}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 进度条 */}
      {task.progress !== undefined && (
        <div className="mt-3">
          <div className="text-[10px] text-muted-foreground mb-1">Progress</div>
          <ProgressDots percentage={task.progress} color={task.progressColor || "bg-gray-400"} />
        </div>
      )}

      {/* 底部信息 */}
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-black/5">
        <AvatarStack count={task.members} />
        <div className="flex items-center gap-2.5 text-muted-foreground">
          <div className="flex items-center gap-1">
            <MessageSquare className="h-3 w-3" />
            <span className="text-[10px]">{task.comments}</span>
          </div>
          <div className="flex items-center gap-1">
            <Paperclip className="h-3 w-3" />
            <span className="text-[10px]">{task.attachments}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
