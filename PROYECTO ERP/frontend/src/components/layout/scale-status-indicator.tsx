/**
 * Indicador del estado de la balanza electrónica (Kretz / Systel / Network).
 *
 * Pollea `/scale/status` cada 30 s vía TanStack Query y muestra un dot Apple-style
 * en la topbar:
 * - emerald → ready con driver real (kretz / systel / network)
 * - amber   → ready en modo mock (dev)
 * - rose    → offline / error / agente caído
 *
 * El tooltip muestra driver, puerto y último peso leído si existe.
 */
import { useQuery } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import { getScaleStatus, type ScaleStatusResponse } from "@/api/agent";
import { cn } from "@/lib/utils";

type Tone = "emerald" | "amber" | "rose";

interface Resolved {
  tone: Tone;
  label: string;
  detail: string;
}

function resolveStatus(
  data: ScaleStatusResponse | undefined,
  isError: boolean,
): Resolved {
  if (isError || !data) {
    return {
      tone: "rose",
      label: "Balanza no detectada",
      detail: "El agente local no respondió a /scale/status",
    };
  }

  if (data.status !== "ready" || !data.online) {
    return {
      tone: "rose",
      label: "Balanza offline",
      detail: data.error ?? data.detail ?? `${data.driver} · ${data.status}`,
    };
  }

  if (data.driver === "mock") {
    return {
      tone: "amber",
      label: "Mock",
      detail: "Sin balanza física asignada — peso simulado para desarrollo",
    };
  }

  const port = data.port ? ` · ${data.port}` : "";
  const last = data.last_weight_kg ? ` · ${data.last_weight_kg} kg` : "";
  return {
    tone: "emerald",
    label: data.model,
    detail: `${data.driver}${port}${last}`,
  };
}

const DOT_COLORS: Record<Tone, string> = {
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
};

export function ScaleStatusIndicator() {
  const query = useQuery({
    queryKey: ["agent-scale-status"],
    queryFn: getScaleStatus,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    retry: 1,
    staleTime: 25_000,
  });

  const { tone, label, detail } = resolveStatus(query.data, query.isError);

  const tooltip = `Balanza: ${label}\n${detail}`;

  return (
    <div
      className="flex items-center gap-1.5 rounded-[8px] px-2 py-1 text-[11px] text-muted-foreground"
      title={tooltip}
      aria-label={tooltip}
    >
      <Scale className="h-[14px] w-[14px]" strokeWidth={1.5} />
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

export default ScaleStatusIndicator;
