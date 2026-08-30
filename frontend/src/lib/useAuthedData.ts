"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./auth";

/** Fetches data with the current access token, exposes loading/error/
 * refetch. Every dashboard page uses this instead of hand-rolling its
 * own useEffect + useState boilerplate for the same pattern. */
export function useAuthedData<T>(fetcher: (token: string) => Promise<T>, deps: unknown[] = []) {
  const { accessToken } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    fetcher(accessToken)
      .then(setData)
      .catch((err) => setError(err?.message ?? "Something went wrong"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, ...deps]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, error, loading, refetch, setData };
}
