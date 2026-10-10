'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { createEventStream } from '@/lib/api';
import { eventKey, MAX_RENDERED_EVENTS } from '@/lib/events';
import type { WorkflowEvent } from '@/lib/types';

export type EventStreamState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'closed';

const INITIAL_RECONNECT_DELAY_MS = 1_000;
const MAX_RECONNECT_DELAY_MS = 30_000;

export function useEventStream(runId: string | null) {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [connectionState, setConnectionState] = useState<EventStreamState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [retryAttempt, setRetryAttempt] = useState(0);
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef(false);
  const retryAttemptRef = useRef(0);
  const seenEventKeysRef = useRef<Set<string>>(new Set());

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    clearReconnectTimer();
    esRef.current?.close();
    esRef.current = null;
    setConnectionState('idle');
  }, [clearReconnectTimer]);

  const connect = useCallback(() => {
    if (!runId || esRef.current) return;

    shouldReconnectRef.current = true;
    clearReconnectTimer();

    const openStream = () => {
      if (!shouldReconnectRef.current || esRef.current) return;

      setConnectionState(retryAttemptRef.current > 0 ? 'reconnecting' : 'connecting');
      const es = createEventStream(runId);
      esRef.current = es;

      es.onopen = () => {
        if (esRef.current !== es) return;
        retryAttemptRef.current = 0;
        setRetryAttempt(0);
        setConnectionState('connected');
        setError(null);
      };

      es.onmessage = (message) => {
        try {
          const event: WorkflowEvent = JSON.parse(message.data);
          const key = eventKey(event);
          if (seenEventKeysRef.current.has(key)) return;

          seenEventKeysRef.current.add(key);
          setEvents((previous) => [...previous, event].slice(-MAX_RENDERED_EVENTS));
        } catch {
          // Ignore malformed telemetry and keep the stream usable.
        }
      };

      es.addEventListener('terminal', () => {
        if (esRef.current !== es) return;
        shouldReconnectRef.current = false;
        clearReconnectTimer();
        es.close();
        esRef.current = null;
        setConnectionState('closed');
      });

      es.onerror = () => {
        if (esRef.current !== es) return;

        es.close();
        esRef.current = null;
        if (!shouldReconnectRef.current) return;

        const nextAttempt = retryAttemptRef.current + 1;
        const delay = Math.min(
          INITIAL_RECONNECT_DELAY_MS * 2 ** (nextAttempt - 1),
          MAX_RECONNECT_DELAY_MS,
        );
        retryAttemptRef.current = nextAttempt;
        setRetryAttempt(nextAttempt);
        setConnectionState('reconnecting');
        setError(`Event stream disconnected; reconnecting in ${Math.round(delay / 1000)}s.`);

        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null;
          openStream();
        }, delay);
      };
    };

    openStream();
  }, [clearReconnectTimer, runId]);

  useEffect(() => {
    seenEventKeysRef.current = new Set();
    retryAttemptRef.current = 0;
    setEvents([]);
    setRetryAttempt(0);
    setError(null);

    if (!runId) {
      setConnectionState('idle');
      return undefined;
    }

    connect();
    return disconnect;
  }, [connect, disconnect, runId]);

  return {
    events,
    connected: connectionState === 'connected',
    connectionState,
    error,
    retryAttempt,
    connect,
    disconnect,
  };
}
