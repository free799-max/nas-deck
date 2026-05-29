/**
 * 顶部栏组件 - Weihu 风格
 *
 * 包含侧边栏收缩按钮、搜索框（内含 ⌘K）、帮助、通知、用户菜单
 */

import { useState, useRef, useEffect } from "react";
import {
  Search,
  Bell,
  HelpCircle,
  PanelLeft,
  PanelLeftClose,
  User,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

interface TopBarProps {
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
}

export function TopBar({ sidebarCollapsed, onToggleSidebar }: TopBarProps) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  /**
   * 点击外部关闭用户菜单
   */
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="h-14 flex items-center justify-between px-6 bg-[#f5f5f5]">
      {/* 左侧：导航收缩按钮 */}
      <div className="w-40 shrink-0 flex items-center">
        <button
          onClick={onToggleSidebar}
          className="h-9 w-9 rounded-xl bg-white flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
          title={sidebarCollapsed ? "展开导航" : "收起导航"}
        >
          {sidebarCollapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* 中间：搜索框，⌘K 在内部右侧 */}
      <div className="flex-1 flex justify-center px-6">
        <div className="relative w-full max-w-2xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Find something"
            className="w-full h-10 pl-9 pr-14 rounded-xl bg-white text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-[#7c3aed]/15 shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)]"
          />
          {/* ⌘K 快捷键提示 - 在搜索框内部右侧 */}
          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-gray-100 text-[10px] text-muted-foreground font-medium">
            <span>⌘</span>
            <span>K</span>
          </div>
        </div>
      </div>

      {/* 右侧：帮助 + 通知 + 用户菜单 */}
      <div className="w-40 shrink-0 flex items-center justify-end gap-2">
        <button className="h-9 w-9 rounded-xl bg-white flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <HelpCircle className="h-4 w-4" />
        </button>
        <button className="h-9 w-9 rounded-xl bg-white flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors relative shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <Bell className="h-4 w-4" />
          <span className="absolute top-2 right-2.5 h-1.5 w-1.5 rounded-full bg-red-500" />
        </button>

        {/* 用户菜单 */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="h-9 px-2.5 rounded-xl bg-white flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
            title={user?.username ?? "用户"}
          >
            <div className="h-5 w-5 rounded-full bg-[#7c3aed]/10 flex items-center justify-center">
              <User className="h-3 w-3 text-[#7c3aed]" />
            </div>
            <span className="text-xs font-medium max-w-[80px] truncate">
              {user?.username ?? "用户"}
            </span>
          </button>

          {/* 下拉菜单 */}
          {menuOpen && (
            <div className="absolute right-0 mt-2 w-40 rounded-xl bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] border border-gray-100 py-1 z-50">
              <div className="px-3 py-2 border-b border-gray-50">
                <p className="text-xs font-medium text-foreground truncate">
                  {user?.username}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {user?.role === "admin" ? "管理员" : "普通用户"}
                </p>
              </div>
              <button
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-destructive hover:bg-red-50 transition-colors"
              >
                <LogOut className="h-3.5 w-3.5" />
                退出登录
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
