import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatPercent } from "@/lib/format";

interface StatCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  variation?: number | null;
  /** Cuando true, una variación NEGATIVA es "buena" (ej. costos). Default false. */
  invertVariation?: boolean;
  loading?: boolean;
  hint?: string;
}

export function StatCard({
  label,
  value,
  icon: Icon,
  variation,
  invertVariation = false,
  loading,
  hint,
}: StatCardProps) {
  const hasVar = variation !== null && variation !== undefined && Number.isFinite(variation);
  const positive = hasVar && (invertVariation ? variation! < 0 : variation! > 0);
  const negative = hasVar && (invertVariation ? variation! > 0 : variation! < 0);
  const TrendIcon = !hasVar
    ? Minus
    : variation! > 0
      ? TrendingUp
      : variation! < 0
        ? TrendingDown
        : Minus;

  return (
    <Card className="p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2 min-w-0">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
          {loading ? (
            <Skeleton className="h-9 w-24" />
          ) : (
            <span className="text-[30px] font-semibold tracking-tight leading-none tabular-nums truncate">
              {value}
            </span>
          )}
          {hint && !loading && (
            <span className="text-[12px] text-muted-foreground">{hint}</span>
          )}
        </div>
        <div className="rounded-[10px] bg-muted/60 p-2 shrink-0">
          <Icon
            className="h-[18px] w-[18px] text-muted-foreground"
            strokeWidth={1.5}
          />
        </div>
      </div>

      {!loading && hasVar && (
        <div
          className={cn(
            "mt-4 inline-flex items-center gap-1 text-[12px] font-medium tabular-nums",
            positive && "text-emerald-600 dark:text-emerald-500",
            negative && "text-rose-600 dark:text-rose-500",
            !positive && !negative && "text-muted-foreground",
          )}
        >
          <TrendIcon className="h-3.5 w-3.5" strokeWidth={2} />
          <span>{formatPercent(variation!, true)}</span>
          <span className="text-muted-foreground font-normal">
            vs período anterior
          </span>
        </div>
      )}
      {!loading && !hasVar && (
        <div className="mt-4 inline-flex items-center gap-1 text-[12px] text-muted-foreground">
          <Minus className="h-3.5 w-3.5" strokeWidth={2} />
          <span>sin datos previos</span>
        </div>
      )}
    </Card>
  );
}
