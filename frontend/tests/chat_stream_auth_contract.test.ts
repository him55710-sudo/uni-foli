import assert from 'node:assert/strict';
import test from 'node:test';

import { AxiosHeaders } from 'axios';

import { applyAuthorizationHeader } from '../src/lib/api';
import { ChatStreamError, openChatEventStream } from '../src/lib/chatStream';
import { getAuthorizationHeader } from '../src/lib/requestAuth';

test('auth helper prefers Firebase token when available', async () => {
  const result = await getAuthorizationHeader({
    firebaseUser: {
      getIdToken: async () => 'firebase-token-123',
    },
    appAccessToken: 'app-token-456',
  });

  assert.equal(result.source, 'firebase');
  assert.equal(result.value, 'Bearer firebase-token-123');
});

test('auth helper falls back to app_access_token when Firebase user is absent', async () => {
  const result = await getAuthorizationHeader({
    appAccessToken: 'app-token-only',
  });

  assert.equal(result.source, 'app_access_token');
  assert.equal(result.value, 'Bearer app-token-only');
});

test('standard API header attachment remains intact for app_access_token fallback', async () => {
  const headers = new AxiosHeaders();
  await applyAuthorizationHeader(headers, { appAccessToken: 'api-token-789' });
  assert.equal(headers.get('Authorization'), 'Bearer api-token-789');
});

test('chat stream surfaces misrouted HTML response with precise diagnostics', async () => {
  await assert.rejects(
    () =>
      openChatEventStream({
        endpoint: 'https://frontend.example.com/api/v1/workshops/abc/chat/stream',
        payload: { message: 'hello' },
        appAccessToken: 'stream-token',
        fetchImpl: async () =>
          new Response('<html><body>frontend app</body></html>', {
            status: 200,
            headers: { 'content-type': 'text/html; charset=utf-8' },
          }),
      }),
    (error: unknown) => {
      assert(error instanceof ChatStreamError);
      assert.equal(error.code, 'backend_misroute');
      assert.match(error.message, /VITE_API_URL/i);
      assert.match(error.detail || '', /frontend app/i);
      return true;
    },
  );
});

test('chat stream rejects non-event-stream content types and keeps auth header wiring', async () => {
  let observedAuthorization: string | null = null;

  await assert.rejects(
    () =>
      openChatEventStream({
        endpoint: 'https://api.example.com/api/v1/drafts/chat/stream',
        payload: { message: 'test' },
        appAccessToken: 'draft-token',
        fetchImpl: async (_input, init) => {
          observedAuthorization = new Headers(init?.headers).get('Authorization');
          return new Response(JSON.stringify({ detail: 'not SSE' }), {
            status: 200,
            headers: { 'content-type': 'application/json' },
          });
        },
      }),
    (error: unknown) => {
      assert(error instanceof ChatStreamError);
      assert.equal(error.code, 'sse_protocol_mismatch');
      assert.match(error.message, /text\/event-stream/i);
      return true;
    },
  );

  assert.equal(observedAuthorization, 'Bearer draft-token');
});
