import { cn } from "@/lib/utils";

interface ConfidenceBarProps {
  value: number | null;
  className?: string;
}

export function ConfidenceBar({ value, className }: ConfidenceBarProps) {
  if (value === null || Number.isNaN(value)) {
    return (
      <div className={cn("text-xs text-muted-foreground", className)}>
        Sin confianza reportada
      </div>
    );
  }
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const tone =
    value >= 0.8
      ? "bg-emerald-500"
      : value >= 0.5
        ? "bg-amber-500"
        : "bg-destructive";
  const label =
    value >= 0.8 ? "Alta" : value >= 0.5 ? "Media" : "Baja";

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Confianza IA</span>
        <span className="font-medium">
          {label} · {pct.toFixed(0)}%
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full transition-all duration-500 ease-apple", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
