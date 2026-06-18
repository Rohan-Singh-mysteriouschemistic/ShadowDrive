import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';

export interface TelemetryData {
  totalNodes: number;
  syncRate: number;
  metrics?: Array<{
    id: string;
    name: string;
    value: string;
    status: 'Healthy' | 'Warning' | 'Critical';
    history: number[];
  }>;
}

export function useTelemetry() {
  return useQuery<TelemetryData>({
    queryKey: ['telemetry'],
    queryFn: async () => {
      const data = await apiFetch('/system/telemetry');
      return {
        totalNodes: data.totalNodes ?? 0,
        syncRate: data.syncRate ?? 0,
        metrics: data.metrics ?? [],
      };
    },
    refetchInterval: 10_000,
  });
}
