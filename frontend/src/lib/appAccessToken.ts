const APP_ACCESS_TOKEN_KEY = 'uni_foli_app_access_token_v1';

export function readAppAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  const token = window.localStorage.getItem(APP_ACCESS_TOKEN_KEY);
  if (!token) return null;
  const normalized = token.trim();
  return normalized.length ? normalized : null;
}

export function writeAppAccessToken(token: string): void {
  if (typeof window === 'undefined') return;
  const normalized = token.trim();
  if (!normalized) return;
  window.localStorage.setItem(APP_ACCESS_TOKEN_KEY, normalized);
}

export function clearAppAccessToken(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(APP_ACCESS_TOKEN_KEY);
}

export function hasAppAccessToken(): boolean {
  return Boolean(readAppAccessToken());
}
