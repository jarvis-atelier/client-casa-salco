/**
 * Hook para detectar/disparar el prompt nativo "Add to Home Screen".
 *
 * Chrome (Android/desktop) emite `beforeinstallprompt`. Lo capturamos,
 * lo guardamos en estado, y exponemos `promptInstall()` para que el botón
 * de la UI lo dispare cuando el user haga click.
 *
 * iOS/Safari NO dispara este evento — para iOS el "agregar a pantalla
 * principal" es manual (Compartir → Añadir). Detectamos iOS para mostrar
 * un hint distinto.
 */
import * as React from "react";

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: "accepted" | "dismissed";
    platform: string;
  }>;
  prompt: () => Promise<void>;
}

declare global {
  interface WindowEventMap {
    beforeinstallprompt: BeforeInstallPromptEvent;
    appinstalled: Event;
  }
}

export interface PwaInstallState {
  /** True si el prompt nativo está disponible (Chrome/Edge/Android). */
  canInstall: boolean;
  /** True si la app ya está instalada / corre en standalone. */
  isInstalled: boolean;
  /** True en iOS Safari (que no soporta beforeinstallprompt). */
  isIOS: boolean;
  /** Dispara el prompt nativo. Devuelve outcome o null si no hay evento. */
  promptInstall: () => Promise<"accepted" | "dismissed" | null>;
}

function detectStandalone(): boolean {
  if (typeof window === "undefined") return false;
  if (window.matchMedia?.("(display-mode: standalone)").matches) return true;
  // iOS legacy
  // @ts-expect-error iOS Safari quirk
  if (typeof window.navigator.standalone === "boolean" && window.navigator.standalone)
    return true;
  return false;
}

function detectIOS(): boolean {
  if (typeof window === "undefined") return false;
  const ua = window.navigator.userAgent;
  return /iPad|iPhone|iPod/.test(ua) && !("MSStream" in window);
}

export function usePwaInstall(): PwaInstallState {
  const [deferred, setDeferred] = React.useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = React.useState<boolean>(detectStandalone);
  const [isIOS] = React.useState<boolean>(detectIOS);

  React.useEffect(() => {
    function onBefore(e: BeforeInstallPromptEvent) {
      e.preventDefault();
      setDeferred(e);
    }
    function onInstalled() {
      setIsInstalled(true);
      setDeferred(null);
    }
    window.addEventListener("beforeinstallprompt", onBefore);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBefore);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const promptInstall = React.useCallback(async () => {
    if (!deferred) return null;
    await deferred.prompt();
    const choice = await deferred.userChoice;
    setDeferred(null);
    return choice.outcome;
  }, [deferred]);

  return {
    canInstall: deferred !== null && !isInstalled,
    isInstalled,
    isIOS,
    promptInstall,
  };
}
