/**
 * 看板页面 Mock 数据和类型定义
 */

export type Tag = {
  label: string;
  color: string;
};

export type Task = {
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

export type Column = {
  id: string;
  title: string;
  tasks: Task[];
};

export const initialColumns: Column[] = [
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

export const teamMembers = [
  { initials: "BS", color: "bg-amber-200" },
  { initials: "CW", color: "bg-blue-300" },
  { initials: "JD", color: "bg-green-300" },
  { initials: "AL", color: "bg-pink-300" },
  { initials: "MK", color: "bg-purple-300" },
];
