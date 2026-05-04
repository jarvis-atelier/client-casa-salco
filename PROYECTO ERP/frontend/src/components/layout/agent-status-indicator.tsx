/**
 * Indicador del estado del agente local de impresión (jarvis-pos-agent).
 *
 * Pollea `/status` cada 30s vía TanStack Query y muestra un dot Apple-style
 * en la topbar:
 * - emerald   → ready (impresora conectada)
 * - amber     → ready pero modo mock (dev)
 * - rose      → offline / error / agente caído
 *
 * El tooltip explica el estado actual.
 */
import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { getPrinterStatus, type PrinterStatusResponse } from "@/api/agent";
import { cn } from "@/lib/utils";

type Tone = "emerald" | "amber" | "rose";

interface Resolved {
  tone: Tone;
  label: string;
  detail: string;
}

function resolveStatus(
  data: PrinterStatusResponse | undefined,
  isError: boolean,
): Resolved {
  if (isError || !data) {
    return {
      tone: "rose",
      label: "Agente caído",
      detail: "No se pudo conectar al agente local en :9123",
    };
  }

  if (data.status !== "ready" || !data.online) {
    return {
      tone: "rose",
      label: "Impresora offline",
      detail: data.detail ?? `${data.driver} · ${data.status}`,
    };
  }

  if (data.driver === "mock") {
    return {
      tone: "amber",
      label: "Modo mock (PDF)",
      detail: "El agente está corriendo pero sin impresora física asignada",
    };
  }

  return {
    tone: "emerald",
    label: `${data.model}`,
    detail: data.detail ?? `Driver ${data.driver}`,
  };
}

const DOT_COLORS: Record<Tone, string> = {
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
};

export function AgentStatusIndicator() {
  const query = useQuery({
    queryKey: ["agent-status"],
    queryFn: getPrinterStatus,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    retry: 1,
    staleTime: 25_000,
  });

  const { tone, label, detail } = resolveStatus(query.data, query.isError);

  const tooltip = `Agente impresión: ${label}\n${detail}`;

  return (
    <div
      className="flex items-center gap-1.5 rounded-[8px] px-2 py-1 text-[11px] text-muted-foreground"
      title={tooltip}
      aria-label={tooltip}
    >
      <Printer className="h-[14px] w-[14px]" strokeWidth={1.5} />
      <span
        className={cn(
          "inline-block h-1.5 w-1.5 rounded-full",
          DOT_COLORS[tone],
          tone === "emerald" && "shadow-[0_0_4px_rgba(16,185,129,0.6)]",
        )}
      />
      <span className="hidden sm:inline tabular-nums">
        {tone === "rose" ? "Offline" : tone === "amber" ? "Mock" : "Online"}
      </span>
    </div>
  );
}

export default AgentStatusIndicator;
