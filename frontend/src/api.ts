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
  const detail = error.response?.data?.detail;
  if (typeof detail !== "string") return fallback;
  if (detail.includes("No features returned")) return "No heat data is available for this site and date yet. Try again shortly.";
  if (detail.includes("UAE compliance checks")) return "Live checks are currently available only for US sites. UAE rules are coming soon.";
  if (detail.includes("Rate limit exceeded")) return "This organization has reached its hourly check limit. Please try again later.";
  if (detail.includes("Only admins or HSE managers")) return "Only admins and HSE managers can add sites.";
  return detail;
}
