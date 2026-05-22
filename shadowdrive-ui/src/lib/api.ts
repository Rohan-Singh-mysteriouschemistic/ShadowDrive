export const BASE_URL = 'http://127.0.0.1:8000';

export function getToken(): string | null {
  return localStorage.getItem('shadowdrive_token');
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token = getToken();
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw response;
  }

  return response.json();
}

async function calculateSHA256(file: File): Promise<string> {
  const arrayBuffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function uploadFile(file: File, remotePath: string) {
  const hash = await calculateSHA256(file);
  
  // 1. Announce metadata
  await apiFetch('/sync/announce', {
    method: 'POST',
    body: JSON.stringify({
      path: remotePath,
      hash: hash,
      event: 'new',
      client_modified_at: new Date().toISOString()
    })
  });
  
  // 2. Upload file binary
  const formData = new FormData();
  formData.append('file', file, remotePath);
  
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  const response = await fetch(`${BASE_URL}/sync/upload`, {
    method: 'POST',
    body: formData,
    headers
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
