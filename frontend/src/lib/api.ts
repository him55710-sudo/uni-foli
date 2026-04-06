import axios, { AxiosHeaders, type AxiosRequestConfig } from 'axios';
import { auth } from './firebase';
import { readAppAccessToken } from './appAccessToken';

function normalizeBaseUrl(value: string) {
  return value.replace(/\/+$/, '');
}

let hasWarnedMissingApiUrl = false;

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
    if (!hasWarnedMissingApiUrl) {
      console.warn(
        'VITE_API_URL is not set. The frontend will call the current origin. Set VITE_API_URL when the API is deployed separately.',
      );
      hasWarnedMissingApiUrl = true;
    }
    return normalizeBaseUrl(origin);
  }

  return 'http://localhost:8000';
}

export function shouldUseSynchronousApiJobs() {
  const explicit = import.meta.env.VITE_SYNC_API_JOBS;
  if (explicit === 'true') return true;
  if (explicit === 'false') return false;

  if (typeof window !== 'undefined' && /\.vercel\.app$/i.test(window.location.hostname)) {
    // Vercel deployments often run without a separate worker process.
    return true;
  }
  return false;
}

const client = axios.create({
  baseURL: resolveApiBaseUrl(),
});

client.interceptors.request.use(
  async (config) => {
    const headers = AxiosHeaders.from(config.headers);
    if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
      // Let the browser set multipart boundaries automatically.
      headers.delete('Content-Type');
    }

    if (auth?.currentUser) {
      const token = await auth.currentUser.getIdToken();
      headers.set('Authorization', `Bearer ${token}`);
    } else {
      const appToken = readAppAccessToken();
      if (appToken) {
        headers.set('Authorization', `Bearer ${appToken}`);
      }
    }
    config.headers = headers;
    return config;
  },
  (error) => Promise.reject(error),
);

async function request<T = any>(config: AxiosRequestConfig): Promise<T> {
  const response = await client.request<T>(config);

  const requestUrl = typeof config.url === 'string' ? config.url : '';
  const contentType = String(response.headers?.['content-type'] || '').toLowerCase();
  if (requestUrl.startsWith('/api/') && contentType.includes('text/html')) {
    throw new Error(
      '백엔드 API 연결이 설정되지 않았습니다. VITE_API_URL을 실제 백엔드 주소로 설정한 뒤 다시 배포해 주세요.',
    );
  }

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
