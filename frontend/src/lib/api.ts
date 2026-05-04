import axios, { AxiosHeaders, type AxiosRequestConfig } from 'axios';
import { auth } from './firebase';
import { getAuthorizationHeader, type AuthorizationHeaderOptions } from './requestAuth';

const viteEnv = ((import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env ??
  {}) as Record<string, string | undefined>;

function normalizeBaseUrl(value: string) {
  return value.replace(/\/+$/, '');
}

function isApiRequestUrl(requestUrl: string): boolean {
  return requestUrl.startsWith('/api/') || /\/api\//.test(requestUrl);
}

let hasWarnedMissingApiUrl = false;

export function resolveApiBaseUrl() {
  const configured = (viteEnv.VITE_API_URL || '').trim();
  if (configured) {
    return normalizeBaseUrl(configured);
  }

  const sameOriginBase = resolveSameOriginApiBaseUrl();
  if (sameOriginBase) {
    if (typeof window !== 'undefined' && !hasWarnedMissingApiUrl) {
      console.warn(
        'VITE_API_URL is not set. The frontend will call the current origin. Set VITE_API_URL when the API is deployed separately.',
      );
      hasWarnedMissingApiUrl = true;
    }
    return sameOriginBase;
  }

  return 'http://localhost:8000';
}

export function getResolvedApiBaseUrl(): string {
  return resolveApiBaseUrl();
}

export function getApiConnectionHint(): string {
  const resolved = getResolvedApiBaseUrl();
  const envValue = (viteEnv.VITE_API_URL || '').trim();
  const isSameOrigin = typeof window !== 'undefined' && resolved === normalizeBaseUrl(window.location.origin);
  
  if (envValue) return `Configured (VITE_API_URL): ${resolved}`;
  if (isSameOrigin) return `Same-Origin: ${resolved}`;
  return `Default: ${resolved}`;
}

export function resolveSameOriginApiBaseUrl(): string | null {
  if (typeof window !== 'undefined') {
    const { protocol, hostname, origin } = window.location;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return normalizeBaseUrl(`${protocol}//${hostname}:8000`);
    }
    return normalizeBaseUrl(origin);
  }
  return null;
}

export function shouldUseSynchronousApiJobs() {
  const explicit = viteEnv.VITE_SYNC_API_JOBS;
  if (explicit === 'true') return true;
  if (explicit === 'false') return false;

  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      // Local runs commonly skip a dedicated worker process.
      return true;
    }
  }
  return false;
}

const client = axios.create({
  baseURL: resolveApiBaseUrl(),
});

export async function applyAuthorizationHeader(
  headers: AxiosHeaders,
  options: AuthorizationHeaderOptions = {},
): Promise<void> {
  const { value } = await getAuthorizationHeader(options);
  if (value) {
    headers.set('Authorization', value);
  } else {
    headers.delete('Authorization');
  }
}

client.interceptors.request.use(
  async (config) => {
    const headers = AxiosHeaders.from(config.headers);
    if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
      // Let the browser set multipart boundaries automatically.
      headers.delete('Content-Type');
    }
    await applyAuthorizationHeader(headers, { firebaseUser: auth?.currentUser });
    config.headers = headers;
    return config;
  },
  (error) => Promise.reject(error),
);

client.interceptors.response.use(
  (response) => {
    assertApiHtmlResponse(response.config, response.headers, response.status);
    return response;
  },
  (error) => {
    if (axios.isAxiosError(error) && error.response) {
      assertApiHtmlResponse(error.config || {}, error.response.headers, error.response.status);
    }
    return Promise.reject(error);
  }
);

function assertApiHtmlResponse(config: AxiosRequestConfig, responseHeaders: any, status: number) {
  const requestUrl = config.url || '';
  const contentType = String(responseHeaders?.['content-type'] || '').toLowerCase();
  
  if (isApiRequestUrl(requestUrl) && contentType.includes('text/html')) {
    const error = new Error(
      `Backend API is returning HTML instead of JSON. This usually means a misconfigured VITE_API_URL or a missing server-side route. ` +
      `[Status: ${status}] [Resolved API Base: ${resolveApiBaseUrl()}] [Request URL: ${requestUrl}]`
    );
    (error as any).debugCode = 'HTML_MISROUTE';
    (error as any).status = status;
    (error as any).contentType = contentType;
    throw error;
  }
}

async function request<T = any>(config: AxiosRequestConfig): Promise<T> {
  const response = await client.request<T>(config);
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

  return {
    blob: response.data,
    contentType: String(response.headers?.['content-type'] || '').toLowerCase(),
    contentDisposition: String(response.headers?.['content-disposition'] || ''),
    status: response.status,
  };
}

export interface RuntimeCapabilities {
  allow_inline_job_processing: boolean;
  async_jobs_inline_dispatch: boolean;
  serverless_runtime: boolean;
  recommended_document_parse_mode: 'sync' | 'async';
  recommended_diagnosis_mode: 'sync' | 'async';
  requires_explicit_process_kicking: boolean;
}

export interface BackendHealthStatus {
  status: 'ok' | 'degraded';
  boot_ok: boolean;
  runtime: {
    app_env: string;
    serverless_runtime: boolean;
    api_prefix: string;
  };
  storage: {
    provider: string;
    bucket?: string | null;
  };
  database: {
    configured: boolean;
    scheme?: string | null;
    allow_production_sqlite: boolean;
    auto_create_tables: boolean;
    connected?: boolean | null;
    error?: string | null;
  };
  llm: {
    default_provider: string;
    guided_chat_provider?: string | null;
    diagnosis_provider?: string | null;
    render_provider?: string | null;
    gemini_api_key_configured?: boolean;
    gemini_model?: string | null;
    ollama_base_url?: string | null;
    ollama_localhost_only?: boolean;
    pdf_analysis_provider?: string | null;
    pdf_analysis_gemini_api_key_configured?: boolean;
    pdf_analysis_ollama_base_url?: string | null;
    pdf_analysis_ollama_localhost_only?: boolean;
    ollama_reachable?: boolean;
    ollama_reason?: string | null;
    ollama_cached?: boolean;
  };
  auth: {
    jwt_configured: boolean;
    firebase_project_configured: boolean;
    firebase_service_account_configured: boolean;
    social_login_enabled: boolean;
  };
  startup: {
    stage: string;
    error_code?: string | null;
    message?: string | null;
    remediation?: string | null;
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
  getRuntimeCapabilities() {
    return api.get<RuntimeCapabilities>('/api/v1/runtime/capabilities');
  },
  getBackendHealth(params?: { check_db?: boolean; check_llm?: boolean }) {
    return api.get<BackendHealthStatus>('/api/v1/health', { params });
  },
  getBackendReadiness(params?: { check_llm?: boolean }) {
    return api.get<BackendHealthStatus>('/api/v1/readiness', { params });
  },
  admin: {
    getMe() {
      return api.get<{ is_admin: boolean; id: string; email?: string | null; name?: string | null }>('/api/v1/admin/me');
    },
    getStats() {
      return api.get<any>('/api/v1/admin/stats');
    },
    listProjects() {
      return api.get<any[]>('/api/v1/admin/projects');
    },
    getProjectAssets(projectId: string) {
      return api.get<{ project: any; uploads: any[]; documents: any[]; diagnosis_runs: any[]; reports: any[] }>(
        `/api/v1/admin/projects/${projectId}/assets`,
      );
    },
    getProjectLogs(projectId: string, limit = 160) {
      return api.get<{ project_id: string; logs: any[] }>(`/api/v1/admin/projects/${projectId}/logs`, { params: { limit } });
    },
    getRecentLogs(limit = 80) {
      return api.get<{ logs: any[] }>('/api/v1/admin/logs/recent', { params: { limit } });
    },
    getRawUploadUrl(uploadId: string) {
      return `${resolveApiBaseUrl()}/api/v1/admin/uploads/${uploadId}/view`;
    },
    getDiagnosisReportUrl(reportId: string) {
      return `${resolveApiBaseUrl()}/api/v1/admin/reports/${reportId}/view`;
    },
  },
};

export default api;
