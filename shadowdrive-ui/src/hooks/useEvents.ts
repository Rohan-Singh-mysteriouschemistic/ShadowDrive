import { useQueryClient } from '@tanstack/react-query';
import { useEventStream } from '../lib/useEventStream';

export function useEventInvalidation() {
  const queryClient = useQueryClient();

  useEventStream((event) => {
    switch (event.type) {
      case 'file_created':
      case 'file_updated':
      case 'file_deleted':
      case 'upload_processing':
      case 'upload_complete':
      case 'upload_failed':
        queryClient.invalidateQueries({ queryKey: ['files'] });
        break;
      case 'conflict_detected':
        queryClient.invalidateQueries({ queryKey: ['conflicts'] });
        queryClient.invalidateQueries({ queryKey: ['files'] });
        break;
    }
  });
}
