/**
 * Hook que expone la cantidad de requests encoladas offline.
 *
 * Pollea `count()` cada 5s (cheap: una sola lectura de IndexedDB).
 * También se refresca en `online` events.
 */
import { useEffect, useState } from "react";
import { count } from "@/lib/offline/queue";

export function useQueueStatus(intervalMs = 5_000): { queued: number } {
  const [queued, setQueued] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const refresh = (): void => {
      count()
        .then((n) => {
          if (!cancelled) setQueued(n);
        })
        .catch(() => {
          /* idb no disponible — ignora */
        });
    };
    refresh();
    const id = setInterval(refresh, intervalMs);
    if (typeof window !== "undefined") {
      window.addEventListener("online", refresh);
      window.addEventListener("offline", refresh);
    }
    return () => {
      cancelled = true;
      clearInterval(id);
      if (typeof window !== "undefined") {
        window.removeEventListener("online", refresh);
        window.removeEventListener("offline", refresh);
      }
    };
  }, [intervalMs]);

  return { queued };
}
