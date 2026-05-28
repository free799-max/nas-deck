/**
 * 应用根组件，配置路由表和鉴权守卫 ProtectedRoute
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "./layouts/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { PluginsPage } from "./pages/PluginsPage";
import { DockerPage } from "./pages/DockerPage";

const queryClient = new QueryClient();

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  // 开发阶段暂时跳过鉴权
  return <>{children}</>;
}

/** 占位页面组件 */
function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-foreground">{title}</h2>
        <p className="text-sm text-muted-foreground mt-2">Coming soon...</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            {/* 核心入口 */}
            <Route path="/" element={<DashboardPage />} />
            <Route path="/services" element={<PluginsPage />} />

            {/* 自动化管理 */}
            <Route
              path="/automation/media"
              element={<PlaceholderPage title="影视" />}
            />
            <Route
              path="/automation/comics"
              element={<PlaceholderPage title="漫画" />}
            />
            <Route
              path="/automation/books"
              element={<PlaceholderPage title="书籍" />}
            />
            <Route
              path="/automation/music"
              element={<PlaceholderPage title="音乐" />}
            />
            <Route
              path="/automation/games"
              element={<PlaceholderPage title="游戏" />}
            />
            <Route
              path="/automation/gallery"
              element={<PlaceholderPage title="图库" />}
            />
            <Route
              path="/automation/news"
              element={<PlaceholderPage title="资讯" />}
            />

            {/* Docker 管理 */}
            <Route
              path="/docker/stacks"
              element={<PlaceholderPage title="容器编排" />}
            />
            <Route path="/docker/containers" element={<DockerPage />} />
            <Route
              path="/docker/images"
              element={<PlaceholderPage title="镜像" />}
            />
            <Route
              path="/docker/host"
              element={<PlaceholderPage title="主机" />}
            />

            {/* 系统设置 */}
            <Route
              path="/settings"
              element={<PlaceholderPage title="系统设置" />}
            />

            {/* 旧路由重定向 */}
            <Route
              path="/docker"
              element={<Navigate to="/docker/containers" replace />}
            />
            <Route
              path="/plugins"
              element={<Navigate to="/services" replace />}
            />
            <Route
              path="/subscriptions"
              element={<Navigate to="/services" replace />}
            />
            <Route
              path="/notifications"
              element={<Navigate to="/settings" replace />}
            />
            <Route
              path="/channels"
              element={<Navigate to="/settings" replace />}
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
