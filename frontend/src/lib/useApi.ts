/**
 * A small fetch hook.
 *
 * Returns the three states every chart needs, so ChartFrame can be handed
 * them directly and the states pass stays mechanical. Deliberately not a data
 * fetching library: the app has a handful of endpoints and no cache
 * invalidation problem worth a dependency.
 */

import { useCallback, useEffect, useState } from "react";

import type { Result } from "./api";

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useApi<T>(
  fetcher: () => Promise<Result<T>>,
  deps: unknown[] = [],
): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcher().then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setData(result.data);
      } else {
        setError(result.error);
      }
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, loading, error, reload };
}
