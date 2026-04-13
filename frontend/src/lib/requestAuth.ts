import { readAppAccessToken } from './appAccessToken';

export type AuthTokenSource = 'firebase' | 'app_access_token' | 'none';

export interface FirebaseTokenUser {
  getIdToken: () => Promise<string>;
}

export interface AuthorizationHeaderOptions {
  firebaseUser?: FirebaseTokenUser | null;
  appAccessToken?: string | null;
  appAccessTokenReader?: () => string | null;
}

export interface AuthorizationHeaderResult {
  source: AuthTokenSource;
  value: string | null;
}

function normalizeToken(value: string | null | undefined): string | null {
  if (!value) return null;
  const normalized = value.trim();
  return normalized.length ? normalized : null;
}

export async function getAuthorizationHeader(
  options: AuthorizationHeaderOptions = {},
): Promise<AuthorizationHeaderResult> {
  const { firebaseUser, appAccessToken, appAccessTokenReader = readAppAccessToken } = options;
  if (firebaseUser) {
    try {
      const firebaseToken = normalizeToken(await firebaseUser.getIdToken());
      if (firebaseToken) {
        return { source: 'firebase', value: `Bearer ${firebaseToken}` };
      }
    } catch (error) {
      console.warn('Failed to read Firebase token. Falling back to app access token.', error);
    }
  }

  const fallbackToken = normalizeToken(appAccessToken ?? appAccessTokenReader());
  if (fallbackToken) {
    return { source: 'app_access_token', value: `Bearer ${fallbackToken}` };
  }

  return { source: 'none', value: null };
}

export async function buildAuthenticatedHeaders(
  baseHeaders?: HeadersInit,
  options: AuthorizationHeaderOptions = {},
): Promise<{ headers: Headers; authSource: AuthTokenSource }> {
  const headers = new Headers(baseHeaders);
  const { source, value } = await getAuthorizationHeader(options);
  if (value) {
    headers.set('Authorization', value);
  } else {
    headers.delete('Authorization');
  }
  return { headers, authSource: source };
}

export async function fetchWithAuth(
  input: RequestInfo | URL,
  init: RequestInit = {},
  options: AuthorizationHeaderOptions = {},
  fetchImpl: typeof fetch = fetch,
): Promise<{ response: Response; authSource: AuthTokenSource }> {
  const { headers, authSource } = await buildAuthenticatedHeaders(init.headers, options);
  const response = await fetchImpl(input, { ...init, headers });
  return { response, authSource };
}
