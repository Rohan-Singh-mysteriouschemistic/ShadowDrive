/**
 * useEventStream — React hook for SSE subscription.
 *
 * Opens a persistent EventSource to /events/stream.
 * On every event, calls the registered handler.
 * Auto-reconnects with exponential backoff on disconnect.
 *
 * Usage:
 *   useEventStream((event) => {
 *     if (event.type === 'file_updated') refreshFiles();
 *   });
 */
import { useEffect, useRef } from 'react';
import { BASE_URL, getToken } from './api';

interface SSEEvent {
  type: string;
  timestamp: string;
  data: Record<string, any>;
}

export function useEventStream(onEvent: (event: SSEEvent) => void) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const reconnectDelay = useRef(1000);

  useEffect(() => {
    let es: EventSource | null = null;
    let closed = false;
    let timeoutId: any = null;

    function connect() {
      if (closed) return;

      const token = getToken();
      if (!token) return;

      // EventSource doesn't support headers, so we pass token as query param
      const url = `${BASE_URL}/events/stream?token=${encodeURIComponent(token)}`;
      es = new EventSource(url);

      es.onopen = () => {
        reconnectDelay.current = 1000; // Reset backoff on successful connect
      };

      // Listen for all named event types
      const eventTypes = [
        'file_created', 'file_updated', 'file_deleted',
        'upload_complete', 'upload_failed', 'upload_processing',
        'conflict_detected', 'heartbeat',
      ];

      for (const type of eventTypes) {
        es.addEventListener(type, (e: MessageEvent) => {
          try {
            const parsed: SSEEvent = JSON.parse(e.data);
            onEventRef.current(parsed);
          } catch (err) {
            console.warn('[SSE] Failed to parse event:', e.data);
          }
        });
      }

      es.onerror = () => {
        es?.close();
        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        const delay = Math.min(reconnectDelay.current, 30000);
        reconnectDelay.current *= 2;
        timeoutId = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      closed = true;
      es?.close();
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, []);
}
