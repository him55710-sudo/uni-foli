import { auth } from './firebase';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = {
  async get(endpoint: string) {
    return fetchWithAuth(endpoint, { method: 'GET' });
  },

  async post(endpoint: string, data: any) {
    return fetchWithAuth(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
      headers: {
        'Content-Type': 'application/json',
      },
    });
  },
};

async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  // Wait for auth to initialize or get current token
  await new Promise(resolve => setTimeout(resolve, 50)); // Tiny delay to ensure auth is ready if calling immediately on mount (fallback)
  const token = await auth.currentUser?.getIdToken();
  const headers = new Headers(options.headers || {});
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(`API Request failed: ${response.statusText}`);
  }

  return response.json();
}
