import {
  fetchWithAuth,
  type AuthTokenSource,
  type AuthorizationHeaderOptions,
} from './requestAuth';

const ERROR_SNIPPET_LIMIT = 280;

export type ChatStreamErrorCode =
  | 'network_error'
  | 'auth_failure'
  | 'backend_startup_failed'
  | 'backend_misroute'
  | 'sse_protocol_mismatch'
  | 'llm_unavailable'
  | 'http_error'
  | 'stream_payload_error';

interface ChatStreamErrorContext {
  endpoint: string;
  status?: number;
  contentType?: string | null;
  detail?: string | null;
  authSource?: AuthTokenSource;
  cause?: unknown;
}

export class ChatStreamError extends Error {
  readonly code: ChatStreamErrorCode;
  readonly endpoint: string;
  readonly status: number | null;
  readonly contentType: string | null;
  readonly detail: string | null;
  readonly authSource: AuthTokenSource | null;

  constructor(code: ChatStreamErrorCode, message: string, context: ChatStreamErrorContext) {
    super(message);
    this.name = 'ChatStreamError';
    this.code = code;
    this.endpoint = context.endpoint;
    this.status = typeof context.status === 'number' ? context.status : null;
    this.contentType = context.contentType ? String(context.contentType) : null;
    this.detail = context.detail ? String(context.detail) : null;
    this.authSource = context.authSource ?? null;
    if (context.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = context.cause;
    }
  }
}

function normalizeContentType(value: string | null): string {
  return String(value || '').toLowerCase();
}

function normalizeSnippet(value: string): string | null {
  const compact = value.replace(/\s+/g, ' ').trim();
  if (!compact) return null;
  if (compact.length <= ERROR_SNIPPET_LIMIT) return compact;
  return `${compact.slice(0, ERROR_SNIPPET_LIMIT)}...`;
}

async function readErrorSnippet(response: Response): Promise<string | null> {
  try {
    return normalizeSnippet(await response.clone().text());
  } catch {
    return null;
  }
}

function looksLikeLlmUnavailable(value: string | null | undefined): boolean {
  if (!value) return false;
  const normalized = value.toLowerCase();
  return (
    normalized.includes('llm_unavailable') ||
    normalized.includes('llm unavailable') ||
    normalized.includes('model unavailable') ||
    normalized.includes('provider unavailable') ||
    normalized.includes('gemini') ||
    normalized.includes('api key')
  );
}

function looksLikeStartupFailure(value: string | null | undefined): boolean {
  if (!value) return false;
  const normalized = value.toLowerCase();
  return (
    normalized.includes('backend_startup_failed') ||
    normalized.includes('database_url_required') ||
    normalized.includes('database_unavailable') ||
    normalized.includes('function_invocation_failed') ||
    normalized.includes('app boot failed') ||
    normalized.includes('startup failed') ||
    normalized.includes('db schema mismatch')
  );
}

function resolveHttpErrorCode(
  status: number,
  detail: string | null,
  response: Response,
): ChatStreamErrorCode {
  const vercelError = response.headers.get('x-vercel-error');
  if (looksLikeStartupFailure(vercelError) || looksLikeStartupFailure(detail)) {
    return 'backend_startup_failed';
  }
  if (status === 401 || status === 403) return 'auth_failure';
  if (looksLikeLlmUnavailable(detail)) return 'llm_unavailable';
  return 'http_error';
}

function resolveHttpErrorMessage(
  status: number,
  detail: string | null,
  response: Response,
): string {
  const vercelError = response.headers.get('x-vercel-error');
  if (looksLikeStartupFailure(vercelError) || looksLikeStartupFailure(detail)) {
    return `Chat backend startup failed before streaming (status ${status}).`;
  }
  if (status === 401 || status === 403) {
    return `Chat stream authorization failed with status ${status}.`;
  }
  if (looksLikeLlmUnavailable(detail)) {
    return `Chat stream backend reported LLM unavailability (status ${status}).`;
  }
  return `Chat stream request failed with status ${status}.`;
}

export interface OpenChatEventStreamParams extends AuthorizationHeaderOptions {
  endpoint: string;
  payload: Record<string, unknown>;
  fetchImpl?: typeof fetch;
}

export interface OpenChatEventStreamResult {
  endpoint: string;
  response: Response;
  authSource: AuthTokenSource;
}

export async function openChatEventStream(
  params: OpenChatEventStreamParams,
): Promise<OpenChatEventStreamResult> {
  const { endpoint, payload, fetchImpl = fetch, ...authOptions } = params;
  let streamResponse: Response;
  let authSource: AuthTokenSource;

  const fetchStream = async (forceFirebaseTokenRefresh: boolean) =>
    fetchWithAuth(
      endpoint,
      {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      },
      {
        ...authOptions,
        forceFirebaseTokenRefresh,
      },
      fetchImpl,
    );

  try {
    const result = await fetchStream(false);
    streamResponse = result.response;
    authSource = result.authSource;

    if ((streamResponse.status === 401 || streamResponse.status === 403) && authSource === 'firebase') {
      const refreshedResult = await fetchStream(true);
      streamResponse = refreshedResult.response;
      authSource = refreshedResult.authSource;
    }
  } catch (error) {
    throw new ChatStreamError('network_error', 'Failed to reach chat stream endpoint.', {
      endpoint,
      cause: error,
    });
  }

  const contentType = normalizeContentType(streamResponse.headers.get('content-type'));
  const vercelError = streamResponse.headers.get('x-vercel-error');
  if (contentType.includes('text/html')) {
    const detail = await readErrorSnippet(streamResponse);
    if (looksLikeStartupFailure(vercelError) || looksLikeStartupFailure(detail)) {
      throw new ChatStreamError(
        'backend_startup_failed',
        'Chat stream backend failed during startup before returning a usable response.',
        {
          endpoint,
          status: streamResponse.status,
          contentType,
          detail,
          authSource,
        },
      );
    }
    throw new ChatStreamError(
      'backend_misroute',
      'Chat stream request returned HTML. VITE_API_URL likely points to the frontend origin instead of the backend API.',
      {
        endpoint,
        status: streamResponse.status,
        contentType,
        detail,
        authSource,
      },
    );
  }

  if (!streamResponse.ok) {
    const detail = await readErrorSnippet(streamResponse);
    const code = resolveHttpErrorCode(streamResponse.status, detail, streamResponse);
    throw new ChatStreamError(code, resolveHttpErrorMessage(streamResponse.status, detail, streamResponse), {
      endpoint,
      status: streamResponse.status,
      contentType,
      detail,
      authSource,
    });
  }

  if (!contentType.includes('text/event-stream')) {
    const detail = await readErrorSnippet(streamResponse);
    throw new ChatStreamError(
      'sse_protocol_mismatch',
      `Chat stream expected content-type text/event-stream but received "${contentType || 'unknown'}".`,
      {
        endpoint,
        status: streamResponse.status,
        contentType,
        detail,
        authSource,
      },
    );
  }

  if (!streamResponse.body) {
    throw new ChatStreamError('sse_protocol_mismatch', 'Chat stream response did not include a readable body.', {
      endpoint,
      status: streamResponse.status,
      contentType,
      authSource,
    });
  }

  return { endpoint, response: streamResponse, authSource };
}

export interface OpenChatEventStreamWithFallbackParams
  extends Omit<OpenChatEventStreamParams, 'endpoint'> {
  endpoints: string[];
}

const RETRYABLE_ENDPOINT_ERROR_CODES = new Set<ChatStreamErrorCode>([
  'network_error',
  'backend_misroute',
  'backend_startup_failed',
]);

function dedupeEndpoints(endpoints: string[]): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const item of endpoints) {
    const endpoint = String(item || '').trim();
    if (!endpoint || seen.has(endpoint)) continue;
    seen.add(endpoint);
    result.push(endpoint);
  }
  return result;
}

export async function openChatEventStreamWithFallback(
  params: OpenChatEventStreamWithFallbackParams,
): Promise<OpenChatEventStreamResult> {
  const { endpoints, ...rest } = params;
  const normalizedEndpoints = dedupeEndpoints(endpoints);
  if (!normalizedEndpoints.length) {
    throw new ChatStreamError('network_error', 'No chat stream endpoint candidates were provided.', {
      endpoint: '',
      detail: 'empty_endpoint_candidates',
    });
  }

  let lastError: ChatStreamError | null = null;
  for (let index = 0; index < normalizedEndpoints.length; index += 1) {
    const endpoint = normalizedEndpoints[index];
    try {
      return await openChatEventStream({
        ...rest,
        endpoint,
      });
    } catch (error) {
      if (!(error instanceof ChatStreamError)) {
        throw error;
      }
      lastError = error;
      const hasNextEndpoint = index < normalizedEndpoints.length - 1;
      if (!hasNextEndpoint || !RETRYABLE_ENDPOINT_ERROR_CODES.has(error.code)) {
        throw error;
      }
    }
  }

  if (lastError) {
    throw lastError;
  }
  throw new ChatStreamError('network_error', 'Failed to open chat stream endpoint.', {
    endpoint: normalizedEndpoints[normalizedEndpoints.length - 1] || '',
  });
}

export interface ChatStreamMetaPayload {
  profile?: string;
  limited_mode?: boolean;
  limited_reason?: string | null;
  coauthoring_mode?: string;
}

export interface ConsumeChatEventStreamParams {
  endpoint: string;
  response: Response;
  authSource?: AuthTokenSource;
  onDelta?: (delta: string) => void;
  onMeta?: (meta: ChatStreamMetaPayload) => void;
  onDraftPatch?: (patch: Record<string, unknown>) => void;
}

export async function consumeChatEventStream(params: ConsumeChatEventStreamParams): Promise<string> {
  const { endpoint, response, authSource, onDelta, onMeta, onDraftPatch } = params;
  if (!response.body) {
    throw new ChatStreamError('sse_protocol_mismatch', 'Chat stream response body is unavailable.', {
      endpoint,
      status: response.status,
      contentType: normalizeContentType(response.headers.get('content-type')),
      authSource,
    });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let full = '';
  let buffer = '';
  let streamDone = false;

  const extractPayloadsFromEvent = (eventChunk: string): Array<Record<string, unknown>> => {
    const dataLines = eventChunk
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.replace(/^data:\s*/, ''));

    if (!dataLines.length) return [];

    const serialized = dataLines.join('\n').trim();
    if (!serialized) return [];

    try {
      const decoded = JSON.parse(serialized);
      return typeof decoded === 'object' && decoded !== null ? [decoded as Record<string, unknown>] : [];
    } catch {
      return [];
    }
  };

  const consumePayload = (payload: Record<string, unknown>) => {
    if (payload.done === true || payload.status === 'DONE') {
      streamDone = true;
      return;
    }

    if (typeof payload.error === 'string' && payload.error.trim()) {
      const detail = payload.error.trim();
      throw new ChatStreamError(
        looksLikeLlmUnavailable(detail) ? 'llm_unavailable' : 'stream_payload_error',
        `Chat stream payload returned an error: ${detail}`,
        {
          endpoint,
          status: response.status,
          contentType: normalizeContentType(response.headers.get('content-type')),
          detail,
          authSource,
        },
      );
    }

    if (payload.meta && typeof payload.meta === 'object') {
      onMeta?.(payload.meta as ChatStreamMetaPayload);
    }

    if (payload.draft_patch && typeof payload.draft_patch === 'object') {
      onDraftPatch?.(payload.draft_patch as Record<string, unknown>);
    }

    const tokenCandidate =
      typeof payload.token === 'string'
        ? payload.token
        : typeof payload.delta === 'string'
          ? payload.delta
          : null;

    if (tokenCandidate) {
      full += tokenCandidate;
      onDelta?.(tokenCandidate);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split('\n\n');
      buffer = chunks.pop() || '';

      for (const eventChunk of chunks) {
        const payloads = extractPayloadsFromEvent(eventChunk);
        for (const payload of payloads) {
          consumePayload(payload);
          if (streamDone) break;
        }
        if (streamDone) break;
      }

      if (streamDone) break;
    }
  } catch (error) {
    const partial = full.trim();
    if (partial) return partial;
    if (error instanceof ChatStreamError) {
      throw error;
    }
    throw new ChatStreamError(
      'stream_payload_error',
      'Chat stream was interrupted before returning a usable response.',
      {
        endpoint,
        status: response.status,
        contentType: normalizeContentType(response.headers.get('content-type')),
        authSource,
        cause: error,
      },
    );
  }

  // Flush decoder tail bytes to avoid partial UTF-8 truncation on stream end.
  buffer += decoder.decode();
  if (buffer.trim()) {
    const chunks = buffer.split('\n\n');
    for (const eventChunk of chunks) {
      const payloads = extractPayloadsFromEvent(eventChunk);
      for (const payload of payloads) {
        consumePayload(payload);
        if (streamDone) break;
      }
      if (streamDone) break;
    }
  }

  return full.trim();
}

export function resolveChatStreamToastMessage(error: ChatStreamError): string {
  const readable = resolveReadableChatStreamToastMessage(error);
  if (readable) return readable;
  if (error.code === 'auth_failure') {
    return '로그인 상태를 확인하지 못했습니다. 페이지를 새로고침한 뒤 다시 시도해 주세요.';
  }
  if (error.code === 'backend_startup_failed') {
    return '채팅 백엔드가 아직 준비되지 않았습니다. 배포 상태와 데이터베이스 설정을 확인해 주세요.';
  }
  if (error.code === 'backend_misroute') {
    return '채팅 요청이 프런트 HTML로 잘못 연결되었습니다. API 주소를 확인해 주세요.';
  }
  if (error.code === 'sse_protocol_mismatch') {
    return '채팅 응답 형식이 올바르지 않습니다. 백엔드 SSE 설정을 확인해 주세요.';
  }
  if (error.code === 'llm_unavailable') {
    return 'AI 모델 연결이 불안정하여 제한 모드 안내로 전환되었습니다.';
  }
  if (error.code === 'network_error') {
    return '채팅 서버에 연결할 수 없습니다. 네트워크 또는 API 주소를 확인해 주세요.';
  }
  return '채팅 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.';
}

export function resolveChatStreamFallbackHint(error: ChatStreamError): string | null {
  const readable = resolveReadableChatStreamFallbackHint(error);
  if (readable) return readable;
  if (error.code === 'auth_failure') {
    return 'Firebase 토큰을 새로고침해도 백엔드 인증을 통과하지 못했습니다.';
  }
  if (error.code === 'backend_startup_failed') {
    return '배포된 백엔드가 부팅에 실패했습니다. DATABASE_URL, 마이그레이션, 서버 상태를 확인해 주세요.';
  }
  if (error.code === 'backend_misroute') {
    return 'VITE_API_URL이 백엔드가 아니라 프런트 origin을 가리키고 있을 수 있습니다.';
  }
  if (error.code === 'sse_protocol_mismatch') {
    return '백엔드가 text/event-stream 대신 일반 응답을 반환했습니다.';
  }
  if (error.code === 'llm_unavailable') {
    return 'LLM 또는 Gemini 연결이 불안정해 제한 모드가 적용되었습니다.';
  }
  return null;
}

function resolveReadableChatStreamToastMessage(error: ChatStreamError): string {
  if (error.code === 'auth_failure') {
    return '로그인 상태를 확인하지 못했어요. 새로고침 후 다시 시도해 주세요.';
  }
  if (error.code === 'backend_startup_failed') {
    return '채팅 백엔드가 아직 준비되지 않았어요. 서버와 데이터베이스 설정을 확인해 주세요.';
  }
  if (error.code === 'backend_misroute') {
    return '채팅 요청이 API가 아닌 화면 경로로 연결됐어요. API 주소 설정을 확인해 주세요.';
  }
  if (error.code === 'sse_protocol_mismatch') {
    return '채팅 응답 형식이 올바르지 않아요. 백엔드 SSE 설정을 확인해 주세요.';
  }
  if (error.code === 'llm_unavailable') {
    return 'Gemini 기반 AI 모델 연결이 불안정해 안전 안내 모드로 전환했어요.';
  }
  if (error.code === 'network_error') {
    return '채팅 서버에 연결할 수 없어요. 백엔드 실행 상태와 API 주소를 확인해 주세요.';
  }
  return '채팅 요청에 실패했어요. 잠시 후 다시 시도해 주세요.';
}

function resolveReadableChatStreamFallbackHint(error: ChatStreamError): string | null {
  if (error.code === 'auth_failure') {
    return 'Firebase 토큰이 백엔드 인증을 통과하지 못했습니다.';
  }
  if (error.code === 'backend_startup_failed') {
    return '백엔드 부팅에 실패했습니다. DATABASE_URL, 마이그레이션, 서버 로그를 확인해 주세요.';
  }
  if (error.code === 'backend_misroute') {
    return 'VITE_API_URL이 백엔드가 아닌 프론트엔드 origin을 가리키는지 확인해 주세요.';
  }
  if (error.code === 'sse_protocol_mismatch') {
    return '백엔드가 text/event-stream 대신 일반 응답을 반환했습니다.';
  }
  if (error.code === 'llm_unavailable') {
    return 'Gemini API 키나 LLM 런타임 설정이 준비되지 않아 제한 모드가 적용됐습니다.';
  }
  return null;
}
