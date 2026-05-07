import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";
import { useAuth, getAccessToken, getRefreshToken } from "@/store/auth";
import { enqueue } from "@/lib/offline/queue";

/**
 * Resuelve un path absoluto del backend respetando el `base` de Vite.
 * En dev (base="/") devuelve `/api/v1/...`; detrás de un reverse-proxy
 * con prefix (`base="/casasalco/"`) devuelve `/casasalco/api/v1/...`.
 */
export function apiPath(path: string): string {
  const base = import.meta.env.BASE_URL || "/";
  const left = base.endsWith("/") ? base.slice(0, -1) : base;
  const right = path.startsWith("/") ? path : `/${path}`;
  return `${left}${right}`;
}

export const apiClient = axios.create({
  baseURL: apiPath("/api/v1"),
  timeout: 15_000,
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

interface RetriableRequest extends InternalAxiosRequestConfig {
  _retried?: boolean;
  /** Marca interna del sync-daemon para no re-encolar al reintentar. */
  _replay?: boolean;
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const { data } = await axios.post<{ access_token: string }>(
      apiPath("/api/v1/auth/refresh"),
      {},
      {
        headers: { Authorization: `Bearer ${refresh}` },
        timeout: 10_000,
      },
    );
    useAuth.getState().setTokens(data.access_token);
    return data.access_token;
  } catch {
    return null;
  }
}

/**
 * Endpoints que NO se encolan offline. Razones:
 *  - `/auth/*`: sin login no podés autenticar nada después.
 *  - `/facturas/`, `/emitir-cae`, `/afip/*`: fiscales — el cajero TIENE que ver
 *    el error y emitir un ticket interno mientras tanto. Encolar daría la
 *    falsa sensación de que la factura salió.
 */
const NO_QUEUE_PATHS = [
  "/auth/login",
  "/auth/refresh",
  "/auth/logout",
  "/facturas/",
  "/emitir-cae",
  "/afip/",
];

function isNetworkError(error: AxiosError): boolean {
  // Sin response = no llegamos al backend (DNS, TCP, timeout, CORS preflight).
  return !error.response;
}

function shouldQueue(url: string, method: string): boolean {
  const m = method.toLowerCase();
  if (!["post", "put", "patch", "delete"].includes(m)) return false;
  return !NO_QUEUE_PATHS.some((p) => url.includes(p));
}

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as RetriableRequest | undefined;

    // ── Cola offline ────────────────────────────────────────────────────────
    // Si la request es mutación, sin response del backend, y el endpoint NO es
    // fiscal, la encolamos y devolvemos 202 sintético "Queued".
    if (
      original &&
      !original._replay &&
      isNetworkError(error) &&
      original.method &&
      shouldQueue(original.url ?? "", original.method)
    ) {
      try {
        let body: unknown = null;
        if (original.data != null) {
          body = typeof original.data === "string" ? JSON.parse(original.data) : original.data;
        }
        // Headers a propagar — sacamos Authorization (se inyecta on-replay
        // con el token vigente al momento del retry).
        const headers: Record<string, string> = {};
        if (original.headers) {
          for (const [k, v] of Object.entries(original.headers)) {
            if (k.toLowerCase() === "authorization") continue;
            if (typeof v === "string") headers[k] = v;
          }
        }
        await enqueue({
          method: original.method.toUpperCase() as "POST" | "PUT" | "PATCH" | "DELETE",
          url: original.url ?? "",
          body,
          headers,
        });
        return Promise.resolve({
          data: { queued: true },
          status: 202,
          statusText: "Queued",
          headers: {},
          config: original,
        });
      } catch {
        // Si idb-keyval falla (browser sin IndexedDB), seguimos al reject normal.
      }
    }

    // ── Refresh 401 ─────────────────────────────────────────────────────────
    if (!original || error.response?.status !== 401 || original._retried) {
      return Promise.reject(error);
    }

    const url = original.url ?? "";
    if (url.includes("/auth/login") || url.includes("/auth/refresh")) {
      return Promise.reject(error);
    }

    original._retried = true;

    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }

    const newToken = await refreshPromise;

    if (!newToken) {
      useAuth.getState().logout();
      return Promise.reject(error);
    }

    original.headers.set("Authorization", `Bearer ${newToken}`);
    return apiClient.request(original as AxiosRequestConfig);
  },
);
