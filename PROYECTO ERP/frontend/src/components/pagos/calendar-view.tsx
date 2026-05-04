import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatMoney } from "@/components/facturas/format";
import { severidadColor } from "./format";
import type { CalendarDay } from "@/lib/types";

interface CalendarViewProps {
  anio: number;
  mes: number; // 1..12
  onMonthChange: (anio: number, mes: number) => void;
  days: CalendarDay[];
  isLoading?: boolean;
  onDayClick: (fecha: string, ids: number[]) => void;
}

const DOW = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const MESES = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

export function CalendarView({
  anio,
  mes,
  onMonthChange,
  days,
  isLoading,
  onDayClick,
}: CalendarViewProps) {
  // Mapa fecha -> CalendarDay
  const dayMap = React.useMemo(() => {
    const m = new Map<string, CalendarDay>();
    for (const d of days) m.set(d.fecha, d);
    return m;
  }, [days]);

  const grid = React.useMemo(() => buildMonthGrid(anio, mes), [anio, mes]);

  const goPrev = () => {
    if (mes === 1) onMonthChange(anio - 1, 12);
    else onMonthChange(anio, mes - 1);
  };
  const goNext = () => {
    if (mes === 12) onMonthChange(anio + 1, 1);
    else onMonthChange(anio, mes + 1);
  };
  const goToday = () => {
    const d = new Date();
    onMonthChange(d.getFullYear(), d.getMonth() + 1);
  };

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(
    2,
    "0",
  )}-${String(today.getDate()).padStart(2, "0")}`;

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={goPrev}
            className="h-8 w-8 p-0"
            aria-label="Mes anterior"
          >
            <ChevronLeft className="h-4 w-4" strokeWidth={1.5} />
          </Button>
          <h3 className="text-[16px] font-semibold tracking-tight capitalize min-w-[180px] text-center">
            {MESES[mes - 1]} {anio}
          </h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={goNext}
            className="h-8 w-8 p-0"
            aria-label="Mes siguiente"
          >
            <ChevronRight className="h-4 w-4" strokeWidth={1.5} />
          </Button>
        </div>
        <Button variant="outline" size="sm" onClick={goToday}>
          Hoy
        </Button>
      </div>

      <div className="grid grid-cols-7 border-b border-border">
        {DOW.map((d) => (
          <div
            key={d}
            className="px-2 py-2 text-[11px] uppercase tracking-wider text-muted-foreground text-center"
          >
            {d}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7">
        {grid.map((cell, i) => {
          if (cell === null) {
            return <div key={`empty-${i}`} className="h-24 border-b border-r border-border bg-muted/20" />;
          }
          const dateStr = `${anio}-${String(mes).padStart(2, "0")}-${String(
            cell,
          ).padStart(2, "0")}`;
          const day = dayMap.get(dateStr);
          const isToday = dateStr === todayStr;
          const inactive = !day;

          return (
            <button
              key={dateStr}
              type="button"
              onClick={() => day && onDayClick(dateStr, day.compromisos_ids)}
              disabled={inactive}
              className={cn(
                "h-24 border-b border-r border-border px-2 py-2 text-left transition-colors duration-150 ease-apple",
                "flex flex-col gap-1 group",
                day
                  ? "hover:bg-muted/40 cursor-pointer"
                  : "bg-card cursor-default text-muted-foreground/60",
                isToday && "bg-primary/5",
              )}
            >
              <span
                className={cn(
                  "text-[12px] tabular-nums",
                  isToday ? "font-semibold text-foreground" : "",
                )}
              >
                {cell}
              </span>
              {day && (
                <div className="flex flex-col gap-0.5 mt-auto">
                  <div className="flex items-center gap-0.5 flex-wrap">
                    {Array.from({ length: Math.min(day.cantidad, 6) }).map(
                      (_, k) => (
                        <span
                          key={k}
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            severidadColor(day.severidad_max),
                          )}
                        />
                      ),
                    )}
                    {day.cantidad > 6 && (
                      <span className="text-[10px] text-muted-foreground ml-0.5">
                        +{day.cantidad - 6}
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] tabular-nums text-muted-foreground truncate">
                    {formatMoney(day.monto_total)}
                  </span>
                </div>
              )}
            </button>
          );
        })}
      </div>

      {isLoading && (
        <div className="border-t border-border px-5 py-2 text-[12px] text-muted-foreground">
          <Skeleton className="h-4 w-32" />
        </div>
      )}
    </Card>
  );
}

/**
 * Construye una grilla de 6x7 (42 celdas) con los días del mes posicionados
 * comenzando en lunes. Las celdas vacías son `null`.
 */
function buildMonthGrid(anio: number, mes: number): (number | null)[] {
  const first = new Date(anio, mes - 1, 1);
  // getDay(): 0=Domingo, 1=Lunes, ..., 6=Sábado.
  // Queremos lunes primero: domingo (0) → 6, lunes (1) → 0, etc.
  const dayOfWeek = first.getDay();
  const offset = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
  const lastDay = new Date(anio, mes, 0).getDate();
  const total = 42;
  const cells: (number | null)[] = [];
  for (let i = 0; i < offset; i++) cells.push(null);
  for (let d = 1; d <= lastDay; d++) cells.push(d);
  while (cells.length < total) cells.push(null);
  return cells;
}
