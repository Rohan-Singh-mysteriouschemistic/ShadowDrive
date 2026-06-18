import { useState, useEffect, useRef } from 'react';
import { useEventStream } from '../lib/useEventStream';
import PageHeader from '../components/PageHeader';

interface NetworkEvent {
  id: string;
  timestamp: string;
  node: string;
  type: 'upload' | 'download' | 'sync' | 'error' | 'heartbeat';
  file?: string;
  size?: string;
  message?: string;
}

interface SSEEvent {
  type: string;
  timestamp: string;
  data: Record<string, any>;
}

function formatEvent(sseEvent: SSEEvent): NetworkEvent {
  const ts = sseEvent.timestamp
    ? new Date(sseEvent.timestamp).toLocaleTimeString()
    : new Date().toLocaleTimeString();

  const node = sseEvent.data?.device_name || sseEvent.data?.node || 'unknown';

  if (sseEvent.type === 'file_created' || sseEvent.type === 'file_updated') {
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: ts,
      node,
      type: 'upload',
      file: sseEvent.data?.file_path,
      size: sseEvent.data?.size_bytes ? `${(sseEvent.data.size_bytes / 1024).toFixed(1)}KB` : undefined,
      message: `${sseEvent.type === 'file_created' ? 'Created' : 'Updated'}: ${sseEvent.data?.file_path || 'unknown'}`,
    };
  }

  if (sseEvent.type === 'file_deleted') {
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: ts,
      node,
      type: 'download',
      message: `Deleted: ${sseEvent.data?.file_path || 'unknown'}`,
    };
  }

  if (sseEvent.type === 'upload_complete') {
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: ts,
      node,
      type: 'sync',
      message: `Upload complete: ${sseEvent.data?.file_path || 'unknown'}`,
    };
  }

  if (sseEvent.type === 'upload_failed') {
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: ts,
      node,
      type: 'error',
      message: `Upload failed: ${sseEvent.data?.file_path || 'unknown'} — ${sseEvent.data?.error || 'unknown error'}`,
    };
  }

  if (sseEvent.type === 'conflict_detected') {
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: ts,
      node,
      type: 'error',
      file: sseEvent.data?.file_path,
      message: `Conflict detected: ${sseEvent.data?.file_path || 'unknown'}`,
    };
  }

  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    timestamp: ts,
    node,
    type: 'heartbeat',
    message: sseEvent.type,
  };
}

export default function NetworkActivity() {
  const [events, setEvents] = useState<NetworkEvent[]>([]);
  const eventsRef = useRef(events);
  eventsRef.current = events;

  useEventStream((sseEvent: SSEEvent) => {
    const formatted = formatEvent(sseEvent);
    setEvents(prev => [formatted, ...prev].slice(0, 200));
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setEvents(prev => prev.map(e => ({ ...e })));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        icon="terminal"
        title="Live Log Stream"
        iconColor="text-primary"
        actions={
          <button
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
            onClick={() => setEvents([])}
          >
            <span className="material-symbols-outlined text-sm">clear_all</span>
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center">
        <div className="w-full max-w-container-max glass-panel rounded-xl overflow-hidden">
          <div className="p-4 font-code-sm text-code-sm space-y-1 min-h-[300px] max-h-[calc(100vh-250px)] overflow-y-auto">
            {events.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-center py-24">
                <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center border border-white/10 mb-4">
                  <span className="material-symbols-outlined text-4xl text-on-surface-variant">
                    cell_tower
                  </span>
                </div>
                <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold mb-2">
                  No Activity Yet
                </h3>
                <p className="font-code-sm text-on-surface-variant max-w-sm">
                  Real-time network events will appear here as files are created, synced, or
                  conflicts are detected across your ShadowDrive network.
                </p>
              </div>
            ) : (
              events.map((ev) => (
                <div
                  key={ev.id}
                  className="flex flex-col sm:flex-row sm:items-center gap-2 p-2 hover:bg-white/5 rounded transition-colors"
                >
                  <span className="text-on-surface-variant opacity-50 w-20 shrink-0">
                    [{ev.timestamp}]
                  </span>
                  <span
                    className={`w-24 shrink-0 font-bold ${
                      ev.type === 'error'
                        ? 'text-error'
                        : ev.type === 'sync'
                          ? 'text-primary'
                          : 'text-[#22d3ee]'
                    }`}
                  >
                    [{ev.type.toUpperCase()}]
                  </span>
                  <span className="text-on-surface truncate">
                    {ev.node}: {ev.message || `Transferred ${ev.file} (${ev.size})`}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
