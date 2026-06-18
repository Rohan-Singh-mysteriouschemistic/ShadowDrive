import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch, uploadFile as uploadFileApi, deleteFile as deleteFileApi } from '../lib/api';

export interface FileRecord {
  id: string | number;
  file_path: string;
  size_bytes: number;
  updated_at: string;
  upload_status: string;
  is_conflict_copy?: boolean;
  storage_path?: string;
}

export function useFiles() {
  return useQuery<FileRecord[]>({
    queryKey: ['files'],
    queryFn: async () => {
      const data = await apiFetch('/sync/metadata');
      return data.map((f: any, idx: number) => ({
        id: f.id || f.hash || idx,
        file_path: f.file_path,
        size_bytes: f.size_bytes,
        updated_at: f.updated_at || new Date().toISOString(),
        upload_status: f.upload_status || 'complete',
        is_conflict_copy: f.file_path?.includes('(Conflicted copy)') || false,
        storage_path: f.storage_path,
      }));
    },
  });
}

export function useUploadFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, remotePath }: { file: File; remotePath: string }) =>
      uploadFileApi(file, remotePath),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}

export function useDeleteFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteFileApi(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}
