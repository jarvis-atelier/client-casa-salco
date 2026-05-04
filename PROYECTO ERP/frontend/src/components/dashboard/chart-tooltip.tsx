import * as React from "react";
import { cn } from "@/lib/utils";

interface AppleTooltipProps {
  title?: React.ReactNode;
  rows?: { label: React.ReactNode; value: React.ReactNode; color?: string }[];
  className?: string;
  children?: React.ReactNode;
}

/**
 * Tooltip estético Apple-styled para usar adentro de Recharts.
 * Recharts pasa `active`, `payload`, `label` al `content`. Acá exponemos la
 * pieza visual; los charts envuelven con la lógica.
 */
export function AppleTooltip({
  title,
  rows,
  className,
  children,
}: AppleTooltipProps) {
  return (
    <div
      className={cn(
        "rounded-[8px] border border-border bg-popover/95 backdrop-blur-md shadow-apple-md p-3 min-w-[180px]",
        "text-[12px] text-popover-foreground",
        className,
      )}
    >
      {title && (
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-2">
          {title}
        </div>
      )}
      {rows?.map((row, i) => (
        <div
          key={i}
          className="flex items-center justify-between gap-4 py-0.5"
        >
          <div className="flex items-center gap-2 min-w-0">
            {row.color && (
              <span
                className="inline-block h-2 w-2 rounded-full shrink-0"
                style={{ background: row.color }}
              />
            )}
            <span className="text-muted-foreground truncate">{row.label}</span>
          </div>
          <span className="tabular-nums font-medium text-foreground">
            {row.value}
          </span>
        </div>
      ))}
      {children}
    </div>
  );
}
