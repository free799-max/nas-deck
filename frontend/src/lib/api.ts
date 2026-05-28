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

// 响应拦截器：处理响应错误，特别是 401 未授权的情况
api.interceptors.response.use(
  // 成功响应直接返回
  (response) => response,
  // 错误响应处理
  (error) => {
    if (error.response?.status === 401) {
      // 收到 401 状态码，说明 token 已失效或未登录
      localStorage.removeItem("token");  // 清除本地存储的 token
      window.location.href = "/login";   // 跳转到登录页
    }
    return Promise.reject(error);
  }
);

export default api;
