/**
 * 全局认证上下文
 *
 * 提供全局登录状态管理：
 * - user: 当前登录用户信息
 * - isLoading: 初始化认证状态中
 * - isAuthenticated: 是否已登录
 * - login(token): 登录后设置状态
 * - logout(): 登出清除状态并跳转
 */

import {
  createContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import api from "@/lib/api";

/** 用户信息类型 */
interface User {
  id: number;
  username: string;
  role: string;
}

/** AuthContext 提供的值 */
interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined
);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  /**
   * 初始化时验证本地 token 是否有效
   * 若 localStorage 中存在 token，调用 /auth/me 验证
   */
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      // 使用 microtask 避免在 effect 中同步 setState
      queueMicrotask(() => setIsLoading(false));
      return;
    }

    api
      .get("/auth/me")
      .then((resp) => setUser(resp.data))
      .catch(() => {
        // token 无效或过期，清除本地存储
        localStorage.removeItem("token");
      })
      .finally(() => setIsLoading(false));
  }, []);

  /**
   * 登录成功后调用，存储 token 并获取用户信息
   */
  const login = useCallback(async (token: string) => {
    localStorage.setItem("token", token);
    const resp = await api.get("/auth/me");
    setUser(resp.data);
  }, []);

  /**
   * 登出：清除本地 token 和用户状态，跳转到登录页
   */
  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setUser(null);
    window.location.href = "/login";
  }, []);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: !!user,
      login,
      logout,
    }),
    [user, isLoading, login, logout]
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}
