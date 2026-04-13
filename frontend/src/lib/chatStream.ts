import {
  fetchWithAuth,
  type AuthTokenSource,
  type AuthorizationHeaderOptions,
} from './requestAuth';

const ERROR_SNIPPET_LIMIT = 280;

export type ChatStreamErrorCode =
  | 'network_error'
  | 'auth_failure'
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

function resolveHttpErrorCode(status: number, detail: string | null): ChatStreamErrorCode {
  if (status === 401 || status === 403) return 'auth_failure';
  if (looksLikeLlmUnavailable(detail)) return 'llm_unavailable';
  return 'http_error';
}

function resolveHttpErrorMessage(status: number, detail: string | null): string {
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
  response: Response;
  authSource: AuthTokenSource;
}

export async function openChatEventStream(
  params: OpenChatEventStreamParams,
): Promise<OpenChatEventStreamResult> {
  const { endpoint, payload, fetchImpl = fetch, ...authOptions } = params;
  let streamResponse: Response;
  let authSource: AuthTokenSource;

  try {
    const result = await fetchWithAuth(
      endpoint,
      {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      },
      authOptions,
      fetchImpl,
    );
    streamResponse = result.response;
    authSource = result.authSource;
  } catch (error) {
    throw new ChatStreamError('network_error', 'Failed to reach chat stream endpoint.', {
      endpoint,
      cause: error,
    });
  }

  const contentType = normalizeContentType(streamResponse.headers.get('content-type'));
  if (contentType.includes('text/html')) {
    const detail = await readErrorSnippet(streamResponse);
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
    const code = resolveHttpErrorCode(streamResponse.status, detail);
    throw new ChatStreamError(code, resolveHttpErrorMessage(streamResponse.status, detail), {
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

  return { response: streamResponse, authSource };
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
  if (error.code === 'auth_failure') {
    return 'Chat authentication expired. Please sign in again and retry.';
  }
  if (error.code === 'backend_misroute') {
    return 'Chat request was routed to frontend HTML. Check VITE_API_URL points to the backend.';
  }
  if (error.code === 'sse_protocol_mismatch') {
    return 'Chat stream response type is invalid. Verify backend SSE configuration.';
  }
  if (error.code === 'llm_unavailable') {
    return 'AI model connectivity is unstable, so limited-mode guidance was used.';
  }
  if (error.code === 'network_error') {
    return 'Could not connect to the chat server. Check network or API URL.';
  }
  return 'Chat request failed. Please retry shortly.';
}

export function resolveChatStreamFallbackHint(error: ChatStreamError): string | null {
  if (error.code === 'auth_failure') {
    return 'Authorization token may be missing or expired.';
  }
  if (error.code === 'backend_misroute') {
    return 'VITE_API_URL may be pointing to the frontend origin instead of the backend API.';
  }
  if (error.code === 'sse_protocol_mismatch') {
    return 'Backend returned a non-SSE response instead of text/event-stream.';
  }
  if (error.code === 'llm_unavailable') {
    return 'LLM/Gemini connectivity is unstable and limited mode was applied.';
  }
  return null;
}
