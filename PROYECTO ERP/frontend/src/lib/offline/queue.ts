/**
 * Cola offline persistente (IndexedDB vía idb-keyval).
 *
 * Cuando se cae internet en una caja, las requests POST/PUT/PATCH/DELETE NO
 * fiscales (o sea: NO facturas AFIP) se encolan acá y se reintentan cuando
 * vuelve la conexión. Sobrevive a refresh y reinicios del browser.
 *
 * Convenciones:
 *  - Cada item tiene un `id` UUID y un prefijo en la key (`jarvis_queue:`)
 *    para no chocar con otras keys de idb-keyval.
 *  - `attempts` se incrementa en cada fallo del sync daemon. Por ahora no hay
 *    tope — se reintenta forever (un humano debería ver el indicador y
 *    decidir).
 *  - Las facturas A/B/C NO se queuean: se bloquean en el POS con un modal.
 */
import { get, set, del, keys } from "idb-keyval";

export interface QueuedRequest {
  /** UUID generado al enqueue. */
  id: string;
  method: "POST" | "PUT" | "PATCH" | "DELETE";
  /** URL relativa o absoluta — la misma que se le pasaría a axios. */
  url: string;
  /** Body parseado (no string). */
  body: unknown;
  /** Headers a reenviar (sin Authorization — se inyecta on-replay). */
  headers: Record<string, string>;
  /** ISO timestamp en que se encoló. */
  createdAt: string;
  /** Cantidad de intentos fallidos. */
  attempts: number;
  /** Último error registrado (para debugging). */
  lastError?: string;
}

const PREFIX = "jarvis_queue:";

function isQueueKey(k: IDBValidKey): k is string {
  return typeof k === "string" && k.startsWith(PREFIX);
}

function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Fallback razonable para entornos sin crypto.randomUUID (tests viejos).
  return `q-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Encola una request para reintento. Devuelve el id asignado. */
export async function enqueue(
  req: Omit<QueuedRequest, "id" | "createdAt" | "attempts">,
): Promise<string> {
  const id = newId();
  const item: QueuedRequest = {
    ...req,
    id,
    createdAt: new Date().toISOString(),
    attempts: 0,
  };
  await set(PREFIX + id, item);
  return id;
}

/** Devuelve todos los items encolados, ordenados por fecha de creación. */
export async function getAll(): Promise<QueuedRequest[]> {
  const allKeys = await keys();
  const queue: QueuedRequest[] = [];
  for (const k of allKeys) {
    if (!isQueueKey(k)) continue;
    const item = await get<QueuedRequest>(k);
    if (item) queue.push(item);
  }
  return queue.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

/** Borra un item ya sincronizado. */
export async function remove(id: string): Promise<void> {
  await del(PREFIX + id);
}

/** Aplica un patch parcial sobre un item existente. */
export async function update(
  id: string,
  patch: Partial<QueuedRequest>,
): Promise<void> {
  const item = await get<QueuedRequest>(PREFIX + id);
  if (item) await set(PREFIX + id, { ...item, ...patch });
}

/** Cantidad de items encolados (útil para UI). */
export async function count(): Promise<number> {
  const all = await getAll();
  return all.length;
}

/** Borra TODA la cola — usar solo en panel de admin / debug. */
export async function clear(): Promise<void> {
  const allKeys = await keys();
  for (const k of allKeys) {
    if (isQueueKey(k)) await del(k);
  }
}
