'use client';

import { useEffect, useState } from 'react';
import { getFinops } from '@/lib/api';
import type { FinOpsSummary } from '@/lib/types';

// In-memory cache keyed by `${runId}:${status}:${tokenUsageCount}` to deduplicate requests across components
const finopsCache = new Map<string, FinOpsSummary>();
const inFlightRequests = new Map<string, Promise<FinOpsSummary>>();

export function useFinops(runId?: string, status?: string, tokenUsageLength?: number) {
  const [finops, setFinops] = useState<FinOpsSummary | null>(() => {
    if (!runId) return null;
    const cacheKey = `${runId}:${status ?? ''}:${tokenUsageLength ?? 0}`;
    return finopsCache.get(cacheKey) ?? null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setFinops(null);
      setLoading(false);
      setError(null);
      return;
    }

    const cacheKey = `${runId}:${status ?? ''}:${tokenUsageLength ?? 0}`;

    if (finopsCache.has(cacheKey)) {
      setFinops(finopsCache.get(cacheKey)!);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    let promise = inFlightRequests.get(cacheKey);
    if (!promise) {
      promise = getFinops(runId)
        .then((data) => {
          finopsCache.set(cacheKey, data);
          return data;
        })
        .finally(() => {
          inFlightRequests.delete(cacheKey);
        });
      inFlightRequests.set(cacheKey, promise);
    }

    promise
      .then((data) => {
        if (!cancelled) {
          setFinops(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setFinops(null);
          setError(err instanceof Error ? err.message : 'Could not load FinOps data.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runId, status, tokenUsageLength]);

  return { finops, loading, error };
}
