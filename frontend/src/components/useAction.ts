import { useRef, useState } from "react";
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const active = useRef(false);
  const last = useRef<(() => Promise<void>) | null>(null);
  async function run(action: () => Promise<void>) {
    if (active.current) return false;
    active.current = true;
    last.current = action;
    setBusy(true);
    setError(null);
    try {
      await action();
      last.current = null;
      return true;
    } catch (e) {
      setError(e);
      return false;
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  return {
    busy,
    error,
    run,
    retry: (): Promise<boolean> =>
      last.current ? run(last.current) : Promise.resolve(false),
    clear: () => {
      last.current = null;
      setError(null);
    },
  };
}
