import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';

export interface SystemNode {
  id: string;
  name: string;
  status: 'Online' | 'Offline';
  lastSeen: string;
}

function formatNode(d: any): SystemNode {
  return {
    id: d.id.toString(),
    name: d.device_name || d.name || 'Unknown',
    status: d.is_online ? 'Online' : 'Offline',
    lastSeen: d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : 'Never',
  };
}

export function useNodes() {
  return useQuery<SystemNode[]>({
    queryKey: ['nodes'],
    queryFn: async () => {
      const data = await apiFetch('/system/nodes');
      return data.map(formatNode);
    },
    refetchInterval: 5000,
  });
}

export function useRenameNode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiFetch(`/devices/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ device_name: name }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nodes'] });
    },
  });
}

export function useSendCommand() {
  return useMutation({
    mutationFn: ({ deviceId, command }: { deviceId: string; command: string }) =>
      apiFetch(`/devices/${deviceId}/command?command=${command}`, {
        method: 'POST',
      }),
  });
}
