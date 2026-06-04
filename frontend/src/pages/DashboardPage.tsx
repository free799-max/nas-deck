/**
 * 看板页面组件 - Weihu 风格 Kanban Board
 *
 * 展示四列看板：Todo list / In Progress / In Review / Done
 */

import { useState } from "react";
import { Plus, MoreHorizontal, MessageSquare, Paperclip, Check } from "lucide-react";

// ===================== 类型定义 =====================

type Tag = {
  label: string;
  color: string;
};

type Task = {
  id: string;
  title: string;
  note?: string;
  tags: Tag[];
  progress?: number;
  progressColor?: string;
  checklist?: { text: string; done: boolean }[];
  members: number;
  comments: number;
  attachments: number;
  bgColor: string;
};

type Column = {
  id: string;
  title: string;
  tasks: Task[];
};

// ===================== Mock 数据 =====================

const initialColumns: Column[] = [
  {
    id: "todo",
    title: "Todo list",
    tasks: [
      {
        id: "t1",
        title: "Search inspirations for upcoming project",
        note: "They like our behance project Mise",
        tags: [
          { label: "#website", color: "bg-blue-100 text-blue-700" },
          { label: "#client", color: "bg-blue-100 text-blue-700" },
        ],
        progress: 40,
        progressColor: "bg-blue-500",
        members: 3,
        comments: 12,
        attachments: 8,
        bgColor: "bg-blue-50/80",
      },
      {
        id: "t2",
        title: "Ginko mobile app design",
        note: "We have a meeting 2:34 AM",
        tags: [
          { label: "#mobile app", color: "bg-violet-100 text-violet-700" },
          { label: "#client", color: "bg-violet-100 text-violet-700" },
        ],
        progress: 15,
        progressColor: "bg-violet-500",
        checklist: [
          { text: "Create user flow", done: true },
          { text: "Make wireframe", done: true },
          { text: "Design onboarding screens", done: false },
          { text: "Make prototype", done: false },
        ],
        members: 3,
        comments: 7,
        attachments: 2,
        bgColor: "bg-violet-50/80",
      },
      {
        id: "t3",
        title: "Make user flow of akua mobile banking app",
        tags: [
          { label: "#mobileapp", color: "bg-rose-100 text-rose-700" },
          { label: "#client", color: "bg-rose-100 text-rose-700" },
        ],
        progress: 30,
        progressColor: "bg-rose-400",
        members: 2,
        comments: 12,
        attachments: 8,
        bgColor: "bg-rose-50/80",
      },
    ],
  },
  {
    id: "inprogress",
    title: "In Progress",
    tasks: [
      {
        id: "p1",
        title: "Weihu product task and the task process pages",
        note: "Have to finish this before weekend",
        tags: [
          { label: "#dribbble shot", color: "bg-amber-100 text-amber-700" },
          { label: "#product", color: "bg-amber-100 text-amber-700" },
        ],
        progress: 90,
        progressColor: "bg-amber-500",
        members: 2,
        comments: 6,
        attachments: 1,
        bgColor: "bg-amber-50/80",
      },
      {
        id: "p2",
        title: "Design CRM shop product page responsive website",
        tags: [
          { label: "#products", color: "bg-teal-100 text-teal-700" },
          { label: "#client", color: "bg-teal-100 text-teal-700" },
        ],
        progress: 40,
        progressColor: "bg-teal-500",
        members: 3,
        comments: 12,
        attachments: 8,
        bgColor: "bg-teal-50/80",
      },
    ],
  },
  {
    id: "inreview",
    title: "In Review",
    tasks: [
      {
        id: "r1",
        title: "Qrypto product landing page create in webflow",
        tags: [
          { label: "#development", color: "bg-pink-100 text-pink-700" },
          { label: "#client", color: "bg-pink-100 text-pink-700" },
        ],
        members: 2,
        comments: 12,
        attachments: 8,
        bgColor: "bg-pink-50/80",
      },
      {
        id: "r2",
        title: "Natverk video platform web app design and develop",
        tags: [
          { label: "#product", color: "bg-violet-100 text-violet-700" },
          { label: "#client", color: "bg-violet-100 text-violet-700" },
        ],
        members: 2,
        comments: 12,
        attachments: 8,
        bgColor: "bg-violet-50/80",
      },
      {
        id: "r3",
        title: "Redesign grab website landing and login pages",
        note: "We have a meeting 3:12 AM",
        tags: [
          { label: "#website", color: "bg-yellow-100 text-yellow-700" },
          { label: "#client", color: "bg-yellow-100 text-yellow-700" },
        ],
        members: 1,
        comments: 12,
        attachments: 8,
        bgColor: "bg-yellow-50/80",
      },
      {
        id: "r4",
        title: "Create Odyah app prototype for Get notification in figma",
        tags: [
          { label: "#mobileapp", color: "bg-violet-100 text-violet-700" },
          { label: "#client", color: "bg-violet-100 text-violet-700" },
        ],
        members: 1,
        comments: 12,
        attachments: 8,
        bgColor: "bg-violet-50/80",
      },
    ],
  },
  {
    id: "done",
    title: "Done",
    tasks: [
      {
        id: "d1",
        title: "Affitto product full service",
        tags: [
          { label: "#mobile app", color: "bg-teal-100 text-teal-700" },
          { label: "#client", color: "bg-teal-100 text-teal-700" },
        ],
        checklist: [
          { text: "Branding", done: true },
          { text: "Mobile app design & development", done: true },
          { text: "Landing page design & development", done: true },
          { text: "Dashboard design & development", done: true },
          { text: "Marketing", done: true },
        ],
        members: 3,
        comments: 7,
        attachments: 2,
        bgColor: "bg-teal-50/80",
      },
      {
        id: "d2",
        title: "Design Moli app product page redesign",
        tags: [
          { label: "#products", color: "bg-rose-100 text-rose-700" },
          { label: "#client", color: "bg-rose-100 text-rose-700" },
        ],
        members: 3,
        comments: 12,
        attachments: 8,
        bgColor: "bg-rose-50/80",
      },
    ],
  },
];

const teamMembers = [
  { initials: "BS", color: "bg-amber-200" },
  { initials: "CW", color: "bg-blue-300" },
  { initials: "JD", color: "bg-green-300" },
  { initials: "AL", color: "bg-pink-300" },
  { initials: "MK", color: "bg-purple-300" },
];

// ===================== 子组件 =====================

function AvatarStack({ count }: { count: number }) {
  const displayCount = Math.min(count, 3);
  return (
    <div className="flex -space-x-1.5">
      {Array.from({ length: displayCount }).map((_, i) => (
        <div
          key={i}
          className={`h-5 w-5 rounded-full border-2 border-white flex items-center justify-center text-[8px] font-medium text-foreground ${
            ["bg-amber-200", "bg-blue-300", "bg-green-300"][i]
          }`}
        />
      ))}
    </div>
  );
}

function ProgressDots({
  percentage,
  color,
}: {
  percentage: number;
  color: string;
}) {
  const total = 10;
  const filled = Math.round(percentage / 10);
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-1">
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            className={`h-1.5 w-1.5 rounded-full ${
              i < filled ? color : "bg-gray-300/60"
            }`}
          />
        ))}
      </div>
      <span className="text-[10px] text-muted-foreground">{percentage}%</span>
    </div>
  );
}

function TaskCard({ task }: { task: Task }) {
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

function KanbanColumn({ column }: { column: Column }) {
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

// ===================== 主页面 =====================

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
