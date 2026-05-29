/**
 * 侧边栏导航组件
 *
 * 导航结构（对应整体架构设计）：
 * - 服务概览 / 服务编排（独立项）
 * - AUTOMATION 分组（7 个媒体类型）
 * - DOCKER 分组（容器编排/管理/镜像/主机）
 * - 系统设置（底部独立项）
 */

import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Server,
  Film,
  BookImage,
  BookOpen,
  Music,
  Gamepad2,
  Images,
  Newspaper,
  Layers,
  Box,
  HardDrive,
  Monitor,
  Settings,
  ChevronDown,
} from "lucide-react";
import { LogoIcon } from "@/components/LogoIcon";

/** 导航项配置 */
interface NavItemConfig {
  path: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

// 顶部独立项：核心入口
const topItems: NavItemConfig[] = [
  { path: "/", label: "服务概览", icon: LayoutDashboard },
  { path: "/services", label: "服务编排", icon: Server },
];

// AUTOMATION 分组：按媒体类型划分的自动化配置
const automationItems: NavItemConfig[] = [
  { path: "/automation/media", label: "影视", icon: Film },
  { path: "/automation/comics", label: "漫画", icon: BookImage },
  { path: "/automation/books", label: "书籍", icon: BookOpen },
  { path: "/automation/music", label: "音乐", icon: Music },
  { path: "/automation/games", label: "游戏", icon: Gamepad2 },
  { path: "/automation/gallery", label: "图库", icon: Images },
  { path: "/automation/news", label: "资讯", icon: Newspaper },
];

// DOCKER 分组：容器与主机管理
const dockerItems: NavItemConfig[] = [
  { path: "/docker/stacks", label: "容器编排", icon: Layers },
  { path: "/docker/containers", label: "容器管理", icon: Box },
  { path: "/docker/images", label: "镜像", icon: HardDrive },
  { path: "/docker/host", label: "主机", icon: Monitor },
];

// 底部独立项
const bottomItems: NavItemConfig[] = [
  { path: "/settings", label: "系统设置", icon: Settings },
];

/** 导航项组件 */
function NavItem({
  item,
  active,
  collapsed,
}: {
  item: NavItemConfig;
  active: boolean;
  collapsed: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link
      to={item.path}
      title={collapsed ? item.label : undefined}
      className={`flex items-center rounded-xl text-sm transition-colors ${
        collapsed ? "justify-center px-2 py-2.5" : "gap-3 px-3 py-2"
      } ${
        active
          ? "bg-[#f5f5f5] text-foreground font-medium"
          : "text-muted-foreground hover:bg-[#f5f5f5]/60 hover:text-foreground"
      }`}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="flex-1">{item.label}</span>}
    </Link>
  );
}

/** 可折叠导航分组 */
function NavGroup({
  title,
  items,
  pathname,
  collapsed,
  onToggle,
  sidebarCollapsed,
  collapsible = true,
  uppercaseTitle = true,
}: {
  title: string;
  items: NavItemConfig[];
  pathname: string;
  collapsed: boolean;
  onToggle: () => void;
  sidebarCollapsed: boolean;
  collapsible?: boolean;
  uppercaseTitle?: boolean;
}) {
  const isGroupActive = items.some(
    (item) => pathname === item.path || pathname.startsWith(item.path + "/")
  );

  if (sidebarCollapsed) {
    return (
      <div className="mt-3">
        {/* 收缩状态下的分组标题首字提示 */}
        <div className="flex items-center justify-center py-1.5">
          <span className="text-[9px] font-semibold text-muted-foreground/60 tracking-wider">
            {title.slice(0, 2)}
          </span>
        </div>
        <div className="space-y-0.5">
          {items.map((item) => (
            <NavItem
              key={item.path}
              item={item}
              active={pathname === item.path}
              collapsed={true}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6">
      <button
        onClick={collapsible ? onToggle : undefined}
        className={`flex items-center w-full px-3 mb-2 text-[11px] font-semibold tracking-wider transition-colors ${
          uppercaseTitle ? "uppercase" : ""
        } ${
          collapsible ? "cursor-pointer" : "cursor-default"
        } ${
          isGroupActive
            ? "text-foreground"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        {title}
        {collapsible && (
          <span
            className={`ml-auto transition-transform duration-300 ease-in-out ${
              collapsed ? "-rotate-90" : "rotate-0"
            }`}
          >
            <ChevronDown className="h-3 w-3" />
          </span>
        )}
      </button>
      <div
        className={`grid overflow-hidden transition-all duration-300 ease-in-out ${
          collapsed ? "grid-rows-[0fr] opacity-0" : "grid-rows-[1fr] opacity-100"
        }`}
      >
        <div className="min-h-0 space-y-0.5">
          {items.map((item) => (
            <NavItem
              key={item.path}
              item={item}
              active={pathname === item.path}
              collapsed={false}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

interface SidebarProps {
  collapsed: boolean;
}

export function Sidebar({ collapsed }: SidebarProps) {
  const location = useLocation();
  const pathname = location.pathname;

  // 折叠状态管理
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(
    new Set()
  );

  const toggleGroup = (title: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });
  };

  return (
    <aside
      className={`flex flex-col h-screen bg-white shadow-[1px_0_0_0_rgba(0,0,0,0.04)] transition-all duration-300 ${
        collapsed ? "w-[60px]" : "w-64"
      }`}
    >
      {/* Logo 区域 */}
      <div
        className={`flex items-center ${
          collapsed ? "justify-center p-4" : "p-6 gap-2.5"
        }`}
      >
        <LogoIcon size={collapsed ? 24 : 28} />
        {!collapsed && (
          <span className="text-lg font-bold text-foreground tracking-tight">
            NasDeck
          </span>
        )}
      </div>

      {/* 导航列表 */}
      <nav className="flex-1 px-3 overflow-y-auto scrollbar-hidden">
        {/* 顶部独立项 */}
        <div className="space-y-0.5">
          {topItems.map((item) => (
            <NavItem
              key={item.path}
              item={item}
              active={
                item.path === "/"
                  ? pathname === "/"
                  : pathname === item.path
              }
              collapsed={collapsed}
            />
          ))}
        </div>

        {/* AUTOMATION 分组 */}
        <NavGroup
          title="自动化配置"
          items={automationItems}
          pathname={pathname}
          collapsed={collapsedGroups.has("AUTOMATION")}
          onToggle={() => toggleGroup("AUTOMATION")}
          sidebarCollapsed={collapsed}
        />

        {/* Docker 分组 */}
        <NavGroup
          title="Docker"
          items={dockerItems}
          pathname={pathname}
          collapsed={false}
          onToggle={() => {}}
          sidebarCollapsed={collapsed}
          collapsible={false}
          uppercaseTitle={false}
        />

        {/* 底部独立项 */}
        <div className={collapsed ? "mt-4 space-y-1" : "mt-6 space-y-0.5"}>
          {bottomItems.map((item) => (
            <NavItem
              key={item.path}
              item={item}
              active={pathname === item.path}
              collapsed={collapsed}
            />
          ))}
        </div>
      </nav>

      {/* 底部用户卡片 */}
      <div className={collapsed ? "p-2" : "p-4"}>
        {collapsed ? (
          <div className="flex justify-center">
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-amber-200 to-orange-300 flex items-center justify-center text-sm font-medium text-foreground">
              E
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-[#f5f5f5]/80 hover:bg-[#f5f5f5] transition-colors cursor-pointer">
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-amber-200 to-orange-300 flex items-center justify-center text-sm font-medium text-foreground">
              E
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-foreground">NasDeck</div>
              <div className="text-xs text-muted-foreground truncate">
                NAS 管理平台
              </div>
            </div>
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
      </div>
    </aside>
  );
}
