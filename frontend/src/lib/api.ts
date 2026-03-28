import axios, { AxiosHeaders, type AxiosRequestConfig } from 'axios';
import { auth } from './firebase';

function normalizeBaseUrl(value: string) {
  return value.replace(/\/+$/, '');
}

export function resolveApiBaseUrl() {
  const configured = import.meta.env.VITE_API_URL;
  if (configured && configured.trim()) {
    return normalizeBaseUrl(configured.trim());
  }

  if (typeof window !== 'undefined') {
    const { protocol, hostname, origin } = window.location;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return `${protocol}//${hostname}:8000`;
    }
    return normalizeBaseUrl(origin);
  }

  return 'http://localhost:8000';
}

const client = axios.create({
  baseURL: resolveApiBaseUrl(),
});

client.interceptors.request.use(
  async (config) => {
    if (auth?.currentUser) {
      const token = await auth.currentUser.getIdToken();
      const headers = AxiosHeaders.from(config.headers);
      headers.set('Authorization', `Bearer ${token}`);
      config.headers = headers;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

async function request<T = any>(config: AxiosRequestConfig): Promise<T> {
  const response = await client.request<T>(config);
  return response.data;
}

export const api = {
  get<T = any>(url: string, config?: AxiosRequestConfig) {
    return request<T>({ ...config, method: 'GET', url });
  },
  post<T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return request<T>({ ...config, method: 'POST', url, data });
  },
  patch<T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return request<T>({ ...config, method: 'PATCH', url, data });
  },
  put<T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return request<T>({ ...config, method: 'PUT', url, data });
  },
};

export default api;
