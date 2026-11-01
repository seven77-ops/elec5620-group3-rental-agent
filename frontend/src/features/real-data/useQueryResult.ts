import { useEffect, useRef, useState } from "react";

/** A changed form or unmounted page can never display an old query as current. */
export function useQueryResult<T>() {
  const [result, setResult] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const revision = useRef(0);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      revision.current++;
    };
  }, []);
  const clear = () => {
    revision.current++;
    setResult(null);
    setError(null);
  };
  const run = async (fetcher: () => Promise<T>) => {
    const token = ++revision.current;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const value = await fetcher();
      if (mounted.current && token === revision.current) setResult(value);
    } catch (e) {
      if (mounted.current && token === revision.current) setError(e);
    } finally {
      if (mounted.current) setBusy(false);
    }
  };
  return { result, error, busy, clear, run };
}
