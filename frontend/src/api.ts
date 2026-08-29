import axios from "axios";

export const TOKEN_KEY = "heatline_access_token";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      if (window.location.pathname !== "/login") window.location.assign("/login");
    }
    return Promise.reject(error);
  },
);

export function apiError(error: unknown, fallback = "Something went wrong. Please try again.") {
  if (!axios.isAxiosError(error)) return fallback;

  const rawDetail = error.response?.data?.detail;
  if (typeof rawDetail === "string" && rawDetail.trim()) return rawDetail;

  const status = error.response?.status;
  if (status === 401) return "Invalid email or password.";
  if (status === 400) return "This request could not be processed. Please check the form and try again.";
  if (status === 403) return "You do not have permission to do that.";
  if (status === 404) return "This resource could not be found.";
  if (status === 429) return "Too many requests. Please wait a moment and try again.";

  if (typeof error.response?.data === "string" && error.response.data.trim()) {
    return error.response.data;
  }

  return fallback;
}
