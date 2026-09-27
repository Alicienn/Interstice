import { useEffect, useState, type DependencyList } from "react";

export type AsyncState<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "ok"; data: T; error: null }
  | { status: "error"; data: null; error: string };

/** Charge une ressource ; ignore les réponses devenues obsolètes. */
export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading", data: null, error: null });
  const [n, setN] = useState(0);
  useEffect(() => {
    let alive = true;
    setState({ status: "loading", data: null, error: null });
    fn().then(
      (data) => alive && setState({ status: "ok", data, error: null }),
      (e: unknown) => alive && setState({ status: "error", data: null, error: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n]);
  return { ...state, reload: () => setN((x) => x + 1) };
}
