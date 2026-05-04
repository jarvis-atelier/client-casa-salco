import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { PackageMinus } from "lucide-react";
import { getReposicion } from "@/api/reposicion";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface Props {
  sucursalId?: number | null;
}

/**
 * Card de dashboard: cantidad de articulos a reponer.
 * Click → navega a /stock/reposicion.
 *
 * Si la cuenta es > 0, se muestra en color rose (atención); sino neutro.
 */
export function ReposicionCard({ sucursalId }: Props) {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["reposicion-resumen", sucursalId],
    queryFn: () => getReposicion(sucursalId ?? undefined),
    staleTime: 60_000,
  });

  const total = data?.totales.articulos_a_reponer ?? 0;
  const valor = data?.totales.valor_estimado ?? "0";

  const valorNum = Number.parseFloat(valor);
  const valorFmt = Number.isFinite(valorNum)
    ? new Intl.NumberFormat("es-AR", {
        style: "currency",
        currency: "ARS",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(valorNum)
    : valor;

  const tone = total > 0 ? "rose" : "neutral";

  return (
    <button
      type="button"
      onClick={() => navigate({ to: "/stock/reposicion" })}
      className="text-left w-full"
    >
      <Card
        className={cn(
          "p-5 transition-colors duration-200 ease-apple cursor-pointer",
          tone === "rose"
            ? "border-rose-500/30 bg-rose-500/5 hover:bg-rose-500/10"
            : "hover:bg-muted/40",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Artículos a reponer
            </span>
            <span
              className={cn(
                "text-[28px] font-semibold tracking-tight tabular-nums leading-none",
                tone === "rose"
                  ? "text-rose-600 dark:text-rose-400"
                  : "text-foreground",
              )}
            >
              {isLoading ? <Skeleton className="h-7 w-16" /> : total}
            </span>
            <span className="text-[12px] text-muted-foreground tabular-nums">
              {isLoading ? (
                <Skeleton className="h-3 w-24" />
              ) : (
                <>Estimado: {valorFmt}</>
              )}
            </span>
          </div>
          <div
            className={cn(
              "rounded-full p-2.5",
              tone === "rose"
                ? "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                : "bg-muted text-muted-foreground",
            )}
          >
            <PackageMinus className="h-5 w-5" strokeWidth={1.5} />
          </div>
        </div>
      </Card>
    </button>
  );
}
