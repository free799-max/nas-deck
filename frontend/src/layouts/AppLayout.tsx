/**
 * 应用整体布局组件 - Weihu 风格
 *
 * 布局结构：
 * ┌──────────────────────────────────┐
 * │  Sidebar  │      TopBar          │
 * │  (左侧)   │─────────────────────│
 * │           │                      │
 * │           │   主内容区 (Outlet)   │
 * │           │                      │
 * └──────────────────────────────────┘
 */

import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppLayout() {
  return (
    <div className="flex h-screen bg-[#f5f5f7]">
      {/* 左侧侧边栏 */}
      <Sidebar />
      {/* 右侧区域 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 顶部栏组件 */}
        <TopBar />
        {/* 主内容区域 */}
        <main className="flex-1 overflow-auto px-8 pb-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
