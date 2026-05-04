/**
 * Indicador Apple-style de estado offline + cola pendiente.
 *
 * - Verde (oculto si todo OK + queue 0)
 * - Ámbar: online pero hay items encolados sincronizando
 * - Rojo:  offline (sin internet)
 *
 * NOTA: este componente NO se monta automáticamente en `topbar.tsx` — la Fase
 * 2.4 (balanzas) está tocando ese archivo en paralelo. El user lo monta a mano
 * después de mergear ambas fases:
 *
 *   // src/components/layout/topbar.tsx
 *   import { OfflineIndicator } from "./offline-indicator";
 *   ...
 *   <ScaleStatusIndicator />
 *   <OfflineIndicator />
 *   <ThemeToggle />
 *
 * TODO: integrar en topbar tras Fase 2.4
 */
import { Cloud, CloudOff, RefreshCw } from "lucide-react";
import { useOnlineStatus } from "@/hooks/use-online-status";
import { useQueueStatus } from "@/hooks/use-queue-status";
import { cn } from "@/lib/utils";

export function OfflineIndicator() {
  const { online } = useOnlineStatus();
  const { queued } = useQueueStatus();

  // Caso ideal: online + sin pendientes → no mostramos nada (silencio Apple).
  if (online && queued === 0) return null;

  let tone: "rose" | "amber" = online ? "amber" : "rose";
  let label = "";
  let detail = "";
  let Icon = CloudOff;

  if (!online) {
    tone = "rose";
    label = queued > 0 ? `Sin internet · ${queued} pendientes` : "Sin internet";
    detail =
      "La caja sigue funcionando con tickets internos. Las facturas A/B/C quedan bloqueadas hasta recuperar conexión.";
    Icon = CloudOff;
  } else {
    tone = "amber";
    label = `Sincronizando · ${queued}`;
    detail = `Se están reenviando ${queued} operaciones que quedaron offline.`;
    Icon = RefreshCw;
  }

  const dotColor = tone === "rose" ? "bg-rose-500" : "bg-amber-500";

  return (
    <div
      className="flex items-center gap-1.5 rounded-[8px] px-2 py-1 text-[11px] text-muted-foreground"
      title={`${label}\n${detail}`}
      aria-label={`${label}. ${detail}`}
      role="status"
    >
      <Icon className="h-[14px] w-[14px]" strokeWidth={1.5} />
      <span
        className={cn(
          "inline-block h-1.5 w-1.5 rounded-full",
          dotColor,
          tone === "amber" && "animate-pulse",
        )}
      />
      <span className="hidden sm:inline tabular-nums">
        {online ? <Cloud className="inline h-3 w-3" /> : "Offline"}
        {queued > 0 ? ` ${queued}` : ""}
      </span>
    </div>
  );
}

export default OfflineIndicator;
