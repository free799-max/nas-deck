/**
 * 登录页面组件
 *
 * 提供用户名/密码登录表单，提交后调用 /auth/login API 进行身份验证。
 * 登录成功后将返回的 access_token 存储到 localStorage，并跳转到首页。
 * 登录失败时显示错误提示信息。
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";

/**
 * 登录页面组件
 *
 * 包含用户名和密码输入框，提交后向后端发起登录请求，
 * 成功后将 token 存入 localStorage 并导航至首页，失败则显示错误信息。
 */
export function LoginPage() {
  // 用户名输入值
  const [username, setUsername] = useState("");
  // 密码输入值
  const [password, setPassword] = useState("");
  // 错误提示信息
  const [error, setError] = useState("");
  // 路由导航钩子，用于登录成功后跳转
  const navigate = useNavigate();

  /**
   * 处理表单提交事件
   *
   * 阻止默认表单行为，向后端 /auth/login 发送用户名和密码。
   * 成功时将 access_token 存入 localStorage 并跳转到首页 "/"。
   * 失败时设置错误提示信息。
   *
   * @param e - React 表单事件对象
   */
  const handleSubmit = async (e: React.FormEvent) => {
    // 阻止表单默认提交行为
    e.preventDefault();
    try {
      // 调用登录接口，发送用户名和密码
      const resp = await api.post("/auth/login", { username, password });
      // 将返回的 access_token 存储到 localStorage，供后续请求鉴权使用
      localStorage.setItem("token", resp.data.access_token);
      // 登录成功，跳转到首页
      navigate("/");
    } catch {
      // 登录失败，显示凭证无效的提示
      setError("Invalid credentials");
    }
  };

  return (
    // 全屏居中布局，使用浅灰色背景
    <div className="min-h-screen flex items-center justify-center bg-muted/30">
      {/* 登录卡片，固定宽度 380px */}
      <Card className="w-[380px]">
        <CardHeader>
          {/* 应用名称标题 */}
          <CardTitle className="text-center">NasDeck</CardTitle>
        </CardHeader>
        <CardContent>
          {/* 登录表单，垂直排列 */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 用户名输入区域 */}
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            {/* 密码输入区域 */}
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {/* 错误提示，仅在登录失败时显示 */}
            {error && <p className="text-sm text-destructive">{error}</p>}
            {/* 登录按钮，宽度占满 */}
            <Button type="submit" className="w-full">
              Login
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
