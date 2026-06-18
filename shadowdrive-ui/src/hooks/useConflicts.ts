import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';

export interface ConflictRecord {
  id: string;
  filename: string;
  path: string;
  timeDetected: string;
  status: 'Needs Resolution' | 'Resolved';
  original_file_id: number;
  conflict_file_id: number;
  optionA: {
    device: string;
    timestamp: string;
    size: string;
    hash: string;
  };
  optionB: {
    device: string;
    timestamp: string;
    size: string;
    hash: string;
  };
}

export function useConflicts() {
  return useQuery<ConflictRecord[]>({
    queryKey: ['conflicts'],
    queryFn: () => apiFetch('/sync/conflicts'),
    refetchInterval: 15_000,
  });
}

export function useResolveConflict() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      original_file_id,
      conflict_file_id,
      resolution_choice,
    }: {
      original_file_id: number;
      conflict_file_id: number;
      resolution_choice: 'keep_original' | 'keep_conflict' | 'keep_both';
    }) =>
      apiFetch('/sync/resolve_conflict', {
        method: 'POST',
        body: JSON.stringify({
          original_file_id,
          conflict_file_id,
          resolution_choice,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conflicts'] });
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}
