/**
 * Axios 实例封装
 *
 * 功能说明：
 * - 创建以 /api 为基础路径的 Axios 实例
 * - 请求拦截器：自动从 localStorage 读取 token 并附加到 Authorization 请求头
 * - 响应拦截器：捕获 401 未授权响应，清除本地 token 并跳转到登录页
 */

import axios from "axios";

// 创建 Axios 实例，所有请求默认以 /api 为前缀
const api = axios.create({
  baseURL: "/api",
});

// 请求拦截器：在每个请求发出前，从 localStorage 中读取 token 并附加到请求头
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    // 若 token 存在，附加 Bearer 认证头
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：解包 StandardResponse 并处理错误
api.interceptors.response.use(
  (response) => {
    // 204 No Content 直接透传
    if (response.status === 204) return response;
    // 提取 data 字段（StandardResponse 包装层）
    if (
      response.data &&
      typeof response.data === "object" &&
      "data" in response.data
    ) {
      response.data = response.data.data;
    }
    return response;
  },
  (error) => {
    if (error.response) {
      const data = error.response.data;
      // 提取后端返回的错误消息
      error.displayMessage = data?.message || "请求失败";

      if (error.response.status === 401) {
        // 排除登录接口本身的 401（让用户界面处理错误提示）
        const isLoginRequest = error.config?.url?.includes("/auth/login");
        if (!isLoginRequest) {
          localStorage.removeItem("token");
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
