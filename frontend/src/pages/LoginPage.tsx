/**
 * 登录页面 — 全新设计
 *
 * 布局：桌面端左右分栏，左侧品牌展示，右侧登录表单
 * 风格：现代极简，紫色主题，弥散光晕，微妙动效
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  User,
  Lock,
  Loader2,
  Eye,
  EyeOff,
  Server,
  Shield,
  Zap,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/toast";
import { LogoIcon } from "@/components/LogoIcon";

/* ------------------------------------------------------------------ */
// 左侧背景浮动粒子组件
function FloatingOrbs() {
  const orbs = [
    { size: 300, x: "10%", y: "20%", delay: 0, duration: 8 },
    { size: 200, x: "70%", y: "60%", delay: 2, duration: 10 },
    { size: 160, x: "40%", y: "80%", delay: 4, duration: 12 },
    { size: 240, x: "80%", y: "15%", delay: 1, duration: 9 },
    { size: 120, x: "25%", y: "45%", delay: 3, duration: 11 },
  ];

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {orbs.map((orb, i) => (
        <div
          key={i}
          className="absolute rounded-full opacity-20 animate-float"
          style={{
            width: orb.size,
            height: orb.size,
            left: orb.x,
            top: orb.y,
            background:
              "radial-gradient(circle, rgba(255,255,255,0.4) 0%, transparent 70%)",
            animationDelay: `${orb.delay}s`,
            animationDuration: `${orb.duration}s`,
          }}
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
// 左侧功能亮点
const features = [
  { icon: Server, text: "海量模板，开箱即用" },
  { icon: Shield, text: "服务编排，丝滑运转" },
  { icon: Zap, text: "订阅自动化，省心省力" },
];

/* ------------------------------------------------------------------ */
export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const navigate = useNavigate();
  const { isAuthenticated, login } = useAuth();
  const toast = useToast();
  const usernameRef = useRef<HTMLInputElement>(null);

  // 已登录则跳转
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // 自动聚焦用户名输入框
  useEffect(() => {
    const t = setTimeout(() => usernameRef.current?.focus(), 300);
    return () => clearTimeout(t);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      toast.error("请输入用户名和密码");
      return;
    }

    setIsLoading(true);
    try {
      const resp = await api.post("/auth/login", { username, password });
      await login(resp.data.access_token);
      toast.success("登录成功，正在跳转...", { duration: 2000 });
      setTimeout(() => navigate("/"), 600);
    } catch {
      toast.error("用户名或密码错误", { duration: 3000 });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* ===================== 左侧品牌区 ===================== */}
      <div className="hidden lg:flex lg:w-[55%] xl:w-1/2 relative bg-primary flex-col justify-between p-12 xl:p-16 overflow-hidden">
        {/* 背景装饰 */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary via-[#6d28d9] to-[#5b21b6]" />
        <FloatingOrbs />

        {/* 顶部 Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-white/15 backdrop-blur-sm flex items-center justify-center">
            <LogoIcon size={24} inverse />
          </div>
          <span className="text-xl font-semibold text-white tracking-tight">
            NasDeck
          </span>
        </div>

        {/* 中部文案 */}
        <div className="relative z-10 max-w-md">
          <h2 className="text-4xl xl:text-5xl font-bold text-white leading-tight tracking-tight">
            掌控您的
            <br />
            <span className="text-white/80">数字生活</span>
          </h2>
          <p className="mt-6 text-lg text-white/70 leading-relaxed">
            告别繁琐配置，NasDeck 让您轻松拥有专属的家庭智能娱乐中心！
            作为一站式自动化编排工具，它提供海量模板，只需一键即可唤醒
            家庭娱乐体验，让一切尽可能在你的掌握之中。
          </p>

          {/* 功能亮点 */}
          <div className="mt-10 space-y-4">
            {features.map((f) => (
              <div
                key={f.text}
                className="flex items-center gap-3 text-white/80"
              >
                <div className="h-8 w-8 rounded-lg bg-white/10 flex items-center justify-center">
                  <f.icon className="h-4 w-4 text-white" />
                </div>
                <span className="text-sm font-medium">{f.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 底部版权 */}
        <div className="relative z-10 text-sm text-white/50">
          © {new Date().getFullYear()} NasDeck. All rights reserved.
        </div>
      </div>

      {/* ===================== 右侧登录区 ===================== */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-10 relative">
        {/* 移动端顶部 Logo */}
        <div className="lg:hidden absolute top-6 left-6 flex items-center gap-2">
          <LogoIcon size={28} />
          <span className="text-lg font-semibold text-foreground">NasDeck</span>
        </div>

        {/* 登录卡片 */}
        <div className="w-full max-w-[400px] animate-fade-in">
          {/* 标题 */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-foreground tracking-tight">
              欢迎回来
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              请输入您的账户信息以继续
            </p>
          </div>

          {/* 表单 */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* 用户名 */}
            <div className="space-y-1.5">
              <label
                htmlFor="username"
                className="block text-sm font-medium text-foreground"
              >
                用户名
              </label>
              <div
                className={`relative group transition-all duration-200 ${
                  focusedField === "username"
                    ? "ring-2 ring-primary/20 rounded-xl"
                    : ""
                }`}
              >
                <div className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 flex items-center justify-center">
                  <User
                    className={`h-4 w-4 transition-colors duration-200 ${
                      focusedField === "username"
                        ? "text-primary"
                        : "text-muted-foreground"
                    }`}
                  />
                </div>
                <input
                  ref={usernameRef}
                  id="username"
                  type="text"
                  placeholder="请输入用户名"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onFocus={() => setFocusedField("username")}
                  onBlur={() => setFocusedField(null)}
                  disabled={isLoading}
                  autoComplete="username"
                  className="w-full h-12 pl-10 pr-4 rounded-xl bg-card border border-border text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all duration-200 focus:border-primary hover:border-border/80 disabled:opacity-50"
                />
              </div>
            </div>

            {/* 密码 */}
            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-sm font-medium text-foreground"
              >
                密码
              </label>
              <div
                className={`relative group transition-all duration-200 ${
                  focusedField === "password"
                    ? "ring-2 ring-primary/20 rounded-xl"
                    : ""
                }`}
              >
                <div className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 flex items-center justify-center">
                  <Lock
                    className={`h-4 w-4 transition-colors duration-200 ${
                      focusedField === "password"
                        ? "text-primary"
                        : "text-muted-foreground"
                    }`}
                  />
                </div>
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="请输入密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setFocusedField("password")}
                  onBlur={() => setFocusedField(null)}
                  disabled={isLoading}
                  autoComplete="current-password"
                  className="w-full h-12 pl-10 pr-10 rounded-xl bg-card border border-border text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all duration-200 focus:border-primary hover:border-border/80 disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            {/* 记住我 & 忘记密码 */}
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer group">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="peer sr-only"
                  />
                  <div className="h-4.5 w-4.5 rounded border border-border bg-card transition-all duration-200 peer-checked:bg-primary peer-checked:border-primary flex items-center justify-center">
                    <CheckCircle2 className="h-3 w-3 text-primary-foreground opacity-0 peer-checked:opacity-100 transition-opacity" />
                  </div>
                </div>
                <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                  记住我
                </span>
              </label>
              <button
                type="button"
                onClick={() =>
                  toast.success("请联系管理员重置密码", { duration: 3000 })
                }
                className="text-sm text-primary hover:text-primary/80 transition-colors font-medium"
              >
                忘记密码？
              </button>
            </div>

            {/* 登录按钮 */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full h-12 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-semibold transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2 group shadow-lg shadow-primary/20 hover:shadow-primary/30 hover:-translate-y-0.5 active:translate-y-0"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>登录中...</span>
                </>
              ) : (
                <>
                  <span>登录</span>
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </button>
          </form>

          {/* 分割线 */}
          <div className="mt-8 flex items-center gap-3">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground uppercase tracking-wider">
              安全登录
            </span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* 安全提示 */}
          <div className="mt-6 flex items-start gap-2.5">
            <Shield className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              您的登录信息将通过加密通道传输。系统会自动检测异常登录行为以保护账户安全。
            </p>
          </div>
        </div>
      </div>

      {/* ===================== 页面级样式 ===================== */}
      <style>{`
        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes float {
          0%, 100% {
            transform: translateY(0) scale(1);
          }
          33% {
            transform: translateY(-20px) scale(1.05);
          }
          66% {
            transform: translateY(10px) scale(0.95);
          }
        }
        .animate-fade-in {
          animation: fade-in 0.5s ease-out;
        }
        .animate-float {
          animation: float ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
