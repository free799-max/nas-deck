/**
 * 顶部栏组件 - Weihu 风格
 *
 * 包含问候语、搜索框（内含 ⌘K）、帮助、通知
 */

import { Search, Bell, HelpCircle } from "lucide-react";

export function TopBar() {
  return (
    <header className="h-16 flex items-center justify-between px-8 bg-[#f5f5f7]">
      {/* 左侧：Welcome */}
      <div className="w-40 shrink-0 leading-tight">
        <div className="text-[11px] text-muted-foreground">Welcome,</div>
        <div className="text-sm font-semibold text-foreground">Brooklyn Simmons</div>
      </div>

      {/* 中间：很长的搜索框，⌘K 在内部右侧 */}
      <div className="flex-1 flex justify-center px-6">
        <div className="relative w-full max-w-2xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Find something"
            className="w-full h-10 pl-9 pr-14 rounded-xl bg-white text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-[#7c3aed]/15 shadow-sm"
          />
          {/* ⌘K 快捷键提示 - 在搜索框内部右侧 */}
          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-gray-100 text-[10px] text-muted-foreground font-medium">
            <span>⌘</span>
            <span>K</span>
          </div>
        </div>
      </div>

      {/* 右侧：帮助 + 通知 */}
      <div className="w-40 shrink-0 flex items-center justify-end gap-2">
        <button className="h-9 w-9 rounded-xl bg-white flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors shadow-sm">
          <HelpCircle className="h-4 w-4" />
        </button>
        <button className="h-9 w-9 rounded-xl bg-white flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors relative shadow-sm">
          <Bell className="h-4 w-4" />
          <span className="absolute top-2 right-2.5 h-1.5 w-1.5 rounded-full bg-red-500" />
        </button>
      </div>
    </header>
  );
}
