/**
 * Daemon que vacía la cola offline cuando hay conexión.
 *
 * Estrategia:
 *  - Drena automáticamente al evento `window.online`.
 *  - Y además cada `intervalMs` (default 15s) hace un poll preventivo, porque
 *    `navigator.onLine` no siempre refleja realidad (puede decir online y aun
 *    así fallar al backend).
 *  - Mutex `syncing` para evitar pisarse a sí mismo.
 *
 * No reintenta forever sin límite: si un item supera `MAX_ATTEMPTS`, queda en
 * la cola pero deja de intentarse (el indicador en UI lo va a delatar). Un
 * humano puede limpiarlo desde un panel de debug.
 */
import { apiClient } from "@/api/client";
import { getAll, remove, update } from "./queue";

const MAX_ATTEMPTS = 50;

let syncing = false;

export interface DrainResult {
  drained: number;
  failed: number;
  remaining: number;
}

/** Drena la cola una vez. Si ya hay un drain en curso, devuelve zeroes. */
export async function drainQueue(): Promise<DrainResult> {
  if (syncing) return { drained: 0, failed: 0, remaining: 0 };
  syncing = true;
  let drained = 0;
  let failed = 0;
  try {
    const queue = await getAll();
    for (const req of queue) {
      if (req.attempts >= MAX_ATTEMPTS) continue;
      try {
        await apiClient.request({
          method: req.method,
          url: req.url,
          data: req.body,
          headers: req.headers,
          // Marca interna para que el interceptor NO re-encole el replay.
          // (Ver `client.ts`.)
          // @ts-expect-error — campo custom propagado por axios sin tipar.
          _replay: true,
        });
        await remove(req.id);
        drained++;
      } catch (err) {
        await update(req.id, {
          attempts: req.attempts + 1,
          lastError: String(err),
        });
        failed++;
      }
    }
    const remaining = (await getAll()).length;
    return { drained, failed, remaining };
  } finally {
    syncing = false;
  }
}

/**
 * Arranca el daemon. Devuelve el handle de setInterval para cleanup en HMR.
 *
 * Llamarlo UNA sola vez al bootstrap de la app (`main.tsx`).
 */
export function startSyncDaemon(intervalMs = 15_000): ReturnType<typeof setInterval> {
  const tick = (): void => {
    drainQueue().catch((err) => {
      // No queremos romper el daemon por un error suelto.
      // eslint-disable-next-line no-console
      console.error("[sync-daemon] drain error:", err);
    });
  };

  if (typeof window !== "undefined") {
    window.addEventListener("online", tick);
    // Drain inicial — por si quedaron requests de una sesión previa.
    tick();
  }

  return setInterval(tick, intervalMs);
}
