import assert from 'node:assert/strict';
import test from 'node:test';

import { AxiosHeaders } from 'axios';

import { api, applyAuthorizationHeader } from '../src/lib/api';
import {
  ChatStreamError,
  consumeChatEventStream,
  openChatEventStream,
  openChatEventStreamWithFallback,
  resolveChatStreamFallbackHint,
  resolveChatStreamToastMessage,
} from '../src/lib/chatStream';
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

test('auth helper can force-refresh a Firebase token for retry flows', async () => {
  const forceRefreshFlags: Array<boolean | undefined> = [];
  const result = await getAuthorizationHeader({
    firebaseUser: {
      getIdToken: async (forceRefresh) => {
        forceRefreshFlags.push(forceRefresh);
        return forceRefresh ? 'fresh-token' : 'cached-token';
      },
    },
    forceFirebaseTokenRefresh: true,
  });

  assert.equal(result.source, 'firebase');
  assert.equal(result.value, 'Bearer fresh-token');
  assert.deepEqual(forceRefreshFlags, [true]);
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

test('chat stream refreshes Firebase auth once when the cached token is rejected', async () => {
  const observedAuthorization: string[] = [];
  const tokenRefreshFlags: Array<boolean | undefined> = [];

  const { response, authSource } = await openChatEventStream({
    endpoint: 'https://api.example.com/api/v1/workshops/w1/chat/stream',
    payload: { message: 'hello' },
    firebaseUser: {
      getIdToken: async (forceRefresh) => {
        tokenRefreshFlags.push(forceRefresh);
        return forceRefresh ? 'fresh-firebase-token' : 'cached-firebase-token';
      },
    },
    fetchImpl: async (_input, init) => {
      const authorization = new Headers(init?.headers).get('Authorization') || '';
      observedAuthorization.push(authorization);

      if (authorization === 'Bearer cached-firebase-token') {
        return new Response(JSON.stringify({ detail: 'Expired token' }), {
          status: 401,
          headers: { 'content-type': 'application/json' },
        });
      }

      return new Response('data: {"done":true}\n\n', {
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
      });
    },
  });

  assert.equal(response.status, 200);
  assert.equal(authSource, 'firebase');
  assert.deepEqual(tokenRefreshFlags, [false, true]);
  assert.deepEqual(observedAuthorization, ['Bearer cached-firebase-token', 'Bearer fresh-firebase-token']);
});

test('chat stream retries a same-flow fallback endpoint after misroute-style HTML response', async () => {
  const primaryEndpoint = 'https://broken.example.com/api/v1/workshops/w1/chat/stream';
  const fallbackEndpoint = 'https://api.example.com/api/v1/workshops/w1/chat/stream';
  const calledEndpoints: string[] = [];

  const { endpoint, response } = await openChatEventStreamWithFallback({
    endpoints: [primaryEndpoint, fallbackEndpoint],
    payload: { message: 'hello' },
    appAccessToken: 'stream-token',
    fetchImpl: async (input) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      calledEndpoints.push(url);

      if (url === primaryEndpoint) {
        return new Response('<html><body>frontend shell</body></html>', {
          status: 200,
          headers: { 'content-type': 'text/html; charset=utf-8' },
        });
      }

      return new Response('data: {"done":true}\n\n', {
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
      });
    },
  });

  assert.equal(endpoint, fallbackEndpoint);
  assert.equal(response.status, 200);
  assert.deepEqual(calledEndpoints, [primaryEndpoint, fallbackEndpoint]);
});

test('chat stream fallback does not retry when authentication fails', async () => {
  let callCount = 0;

  await assert.rejects(
    () =>
      openChatEventStreamWithFallback({
        endpoints: [
          'https://api.example.com/api/v1/workshops/w1/chat/stream',
          'https://api.example.com/api/v1/workshops/w1/chat/stream?retry=1',
        ],
        payload: { message: 'hello' },
        appAccessToken: 'stream-token',
        fetchImpl: async () => {
          callCount += 1;
          return new Response(JSON.stringify({ detail: 'Unauthorized' }), {
            status: 401,
            headers: { 'content-type': 'application/json' },
          });
        },
      }),
    (error: unknown) => {
      assert(error instanceof ChatStreamError);
      assert.equal(error.code, 'auth_failure');
      return true;
    },
  );

  assert.equal(callCount, 1);
});

test('chat stream keeps partial text when the response closes abruptly after tokens', async () => {
  const encoded = new TextEncoder().encode('data: {"token":"partial reply"}\n\n');
  let sent = false;
  const response = new Response(
    new ReadableStream({
      pull(controller) {
        if (sent) {
          controller.error(new Error('stream interrupted'));
          return;
        }
        sent = true;
        controller.enqueue(encoded);
      },
    }),
    {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    },
  );

  const deltas: string[] = [];
  const result = await consumeChatEventStream({
    endpoint: 'https://api.example.com/api/v1/workshops/w1/chat/stream',
    response,
    onDelta: (delta) => deltas.push(delta),
  });

  assert.equal(result, 'partial reply');
  assert.deepEqual(deltas, ['partial reply']);
});

test('chat stream classifies backend startup failures separately from generic HTTP errors', async () => {
  await assert.rejects(
    () =>
      openChatEventStream({
        endpoint: 'https://api.example.com/api/v1/workshops/boot/chat/stream',
        payload: { message: 'test' },
        appAccessToken: 'stream-token',
        fetchImpl: async () =>
          new Response(JSON.stringify({ detail: { code: 'BACKEND_STARTUP_FAILED' } }), {
            status: 500,
            headers: {
              'content-type': 'application/json',
              'x-vercel-error': 'FUNCTION_INVOCATION_FAILED',
            },
          }),
      }),
    (error: unknown) => {
      assert(error instanceof ChatStreamError);
      assert.equal(error.code, 'backend_startup_failed');
      assert.match(resolveChatStreamToastMessage(error), /백엔드가 아직 준비되지 않았습니다/);
      assert.match(resolveChatStreamFallbackHint(error) || '', /DATABASE_URL|마이그레이션|서버 상태/);
      return true;
    },
  );
});

test('standard API surfaces misrouted HTML responses with backend diagnostics', async () => {
  await assert.rejects(
    () =>
      api.get('/api/v1/runtime/capabilities', {
        adapter: async (config) =>
          ({
            data: '<html><body>frontend shell</body></html>',
            status: 200,
            statusText: 'OK',
            headers: { 'content-type': 'text/html; charset=utf-8' },
            config,
            request: {},
          }) as any,
      }),
    (error: unknown) => {
      assert(error instanceof Error);
      assert.match(error.message, /VITE_API_URL/i);
      assert.match(error.message, /HTML/i);
      return true;
    },
  );
});
