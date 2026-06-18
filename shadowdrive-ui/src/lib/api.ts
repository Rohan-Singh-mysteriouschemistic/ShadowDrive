export const BASE_URL = 'http://127.0.0.1:8000';

let inMemoryToken: string | null = null;

export function getToken(): string | null {
  return inMemoryToken;
}

export function setToken(token: string | null) {
  inMemoryToken = token;
}

async function fetchTokenFromServer(): Promise<void> {
  try {
    const response = await fetch('http://127.0.0.1:8001/api/auth/token');
    if (response.ok) {
      const data = await response.json();
      inMemoryToken = data.access_token;
    }
  } catch (err) {
    console.error('[Token fetch] Failed to fetch token from local client api', err);
  }
}

/**
 * Retry wrapper for API calls.
 * Retries on network errors and 5xx status codes.
 * Uses exponential backoff with jitter.
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  baseDelay = 1000,
): Promise<T> {
  let lastError: any;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err: any) {
      lastError = err;

      // Don't retry client errors (4xx) — they won't change
      if (err instanceof Response && err.status >= 400 && err.status < 500) {
        throw err;
      }

      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt - 1);
        const jitter = delay * 0.5 * (Math.random() * 2 - 1);
        await new Promise(r => setTimeout(r, Math.max(100, delay + jitter)));
      }
    }
  }

  throw lastError;
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  if (inMemoryToken === null) {
    await fetchTokenFromServer();
  }

  const doFetch = async () => {
    const token = getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });
    if (!response.ok) throw response;
    return response.json();
  };

  try {
    return await withRetry(doFetch);
  } catch (err: any) {
    if (err instanceof Response && err.status === 401) {
      // Token likely expired, try refreshing
      const token = getToken();
      if (token) {
        try {
          const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
          });
          
          if (refreshRes.ok) {
            const data = await refreshRes.json();
            inMemoryToken = data.access_token;
            // Retry the original request with the new token
            return await withRetry(doFetch);
          }
        } catch (refreshErr) {
          console.error('[JWT Refresh] Failed to contact refresh endpoint', refreshErr);
        }
      }
    }
    // If not a 401, or if refresh failed, throw the original error
    throw err;
  }
}

export async function uploadFile(file: File, remotePath: string) {
  const formData = new FormData();
  // Pass the file so the local API can drop it in the watch_folder
  formData.append('file', file, remotePath);

  const response = await fetch(`http://127.0.0.1:8001/api/upload`, {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) throw response;
  return response.json();
}

export async function deleteFile(id: string) {
  return apiFetch(`/sync/file/${id}`, {
    method: 'DELETE'
  });
}

export function getDownloadUrl(storagePath: string) {
  const token = getToken();
  // Using query param for token in window download flow
  return `${BASE_URL}/sync/download?storage_path=${encodeURIComponent(storagePath)}&token=${token || ''}`;
}
