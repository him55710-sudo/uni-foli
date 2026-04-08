import axios, { AxiosHeaders, type AxiosRequestConfig } from 'axios';
import { auth } from './firebase';
import { readAppAccessToken } from './appAccessToken';

function normalizeBaseUrl(value: string) {
  return value.replace(/\/+$/, '');
}

function isApiRequestUrl(requestUrl: string): boolean {
  return requestUrl.startsWith('/api/') || /\/api\//.test(requestUrl);
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

  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      // Local runs commonly skip a dedicated worker process.
      return true;
    }
    if (/\.vercel\.app$/i.test(hostname)) {
      // Vercel deployments often run without a separate worker process.
      return true;
    }
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

function assertApiHtmlResponse(requestUrl: string, contentType: string) {
  if (isApiRequestUrl(requestUrl) && contentType.includes('text/html')) {
    throw new Error(
      'Backend API is returning HTML. Check VITE_API_URL and make sure it points to the backend origin.',
    );
  }
}

async function request<T = any>(config: AxiosRequestConfig): Promise<T> {
  const response = await client.request<T>(config);
  const requestUrl = typeof config.url === 'string' ? config.url : '';
  const contentType = String(response.headers?.['content-type'] || '').toLowerCase();
  assertApiHtmlResponse(requestUrl, contentType);
  return response.data;
}

export interface ApiDownloadResponse {
  blob: Blob;
  contentType: string;
  contentDisposition: string;
  status: number;
}

async function download(url: string, config?: AxiosRequestConfig): Promise<ApiDownloadResponse> {
  const response = await client.request<Blob>({
    ...config,
    method: 'GET',
    url,
    responseType: 'blob',
  });

  const contentType = String(response.headers?.['content-type'] || '').toLowerCase();
  assertApiHtmlResponse(url, contentType);

  return {
    blob: response.data,
    contentType,
    contentDisposition: String(response.headers?.['content-disposition'] || ''),
    status: response.status,
  };
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
  download(url: string, config?: AxiosRequestConfig) {
    return download(url, config);
  },
};

export default api;
