/**
 * Detección de plataforma — sirve para condicionar comportamiento entre la
 * versión web (PWA) y la versión empaquetada como app nativa con Tauri.
 *
 * Tauri 2.x inyecta `__TAURI_INTERNALS__` en `window` cuando corre dentro del
 * shell nativo. En el navegador esa propiedad no existe.
 */

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

/** True si estamos corriendo dentro de la app desktop (Tauri). */
export const isTauri = (): boolean => {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
};

/** Nombre de la plataforma actual. Útil para logs / telemetría. */
export const platformName = (): "tauri" | "web" => (isTauri() ? "tauri" : "web");

/** True si estamos en un browser standalone PWA (instalada). */
export const isStandalonePWA = (): boolean => {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    // iOS Safari
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
};
