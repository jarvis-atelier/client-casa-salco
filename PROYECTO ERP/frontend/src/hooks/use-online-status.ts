/**
 * Hook reactivo de estado de conexión.
 *
 * Usa los eventos nativos `online` / `offline` del browser. Es el mismo
 * mecanismo en Tauri (WebView2 propaga el estado del sistema).
 */
import { useEffect, useState } from "react";

export interface OnlineStatus {
  online: boolean;
  /** Última vez que cambió el estado — útil para mostrar "desde hace X". */
  lastChange: Date;
}

export function useOnlineStatus(): OnlineStatus {
  const [online, setOnline] = useState<boolean>(
    typeof navigator !== "undefined" ? navigator.onLine : true,
  );
  const [lastChange, setLastChange] = useState<Date>(() => new Date());

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = (): void => {
      setOnline(navigator.onLine);
      setLastChange(new Date());
    };
    window.addEventListener("online", handler);
    window.addEventListener("offline", handler);
    return () => {
      window.removeEventListener("online", handler);
      window.removeEventListener("offline", handler);
    };
  }, []);

  return { online, lastChange };
}
