import * as React from "react";
import { Clock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AppleTooltip } from "./chart-tooltip";
import {
  DIA_SEMANA_LONG,
  DIA_SEMANA_SHORT,
  formatARSDetail,
  formatNumber,
} from "@/lib/format";
import type { VentasPorHora } from "@/api/reports";

interface HorasHeatmapProps {
  data: VentasPorHora[] | undefined;
  loading: boolean;
}

interface CellData {
  cantidad: number;
  total: number;
}

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const DOW = [0, 1, 2, 3, 4, 5, 6];

export function HorasHeatmap({ data, loading }: HorasHeatmapProps) {
  const grid = React.useMemo<CellData[][]>(() => {
    const matrix: CellData[][] = DOW.map(() =>
      HOURS.map(() => ({ cantidad: 0, total: 0 })),
    );
    if (!data) return matrix;
    for (const row of data) {
      const dow = Math.max(0, Math.min(6, row.dia_semana));
      const h = Math.max(0, Math.min(23, row.hora));
      matrix[dow][h] = {
        cantidad: row.cantidad,
        total: parseFloat(row.total) || 0,
      };
    }
    return matrix;
  }, [data]);

  const maxCantidad = React.useMemo(() => {
    let m = 0;
    for (const row of grid)
      for (const cell of row) if (cell.cantidad > m) m = cell.cantidad;
    return m;
  }, [grid]);

  const isEmpty = !loading && maxCantidad === 0;

  const [hover, setHover] = React.useState<{
    dow: number;
    hour: number;
    rect: DOMRect;
  } | null>(null);

  return (
    <Card className="p-6 flex flex-col">
      <div className="flex items-center gap-3 mb-4">
        <div className="rounded-[10px] bg-primary/10 p-2 shrink-0">
          <Clock
            className="h-[18px] w-[18px] text-primary"
            strokeWidth={1.5}
          />
        </div>
        <div>
          <h3 className="text-[15px] font-semibold tracking-tight leading-tight">
            Horas pico
          </h3>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            Densidad de ventas por día y hora
          </p>
        </div>
      </div>

      {loading ? (
        <Skeleton className="h-[230px] w-full" />
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center h-[230px] text-muted-foreground">
          <div className="rounded-full bg-muted/60 p-3 mb-3">
            <Clock className="h-5 w-5 opacity-50" strokeWidth={1.5} />
          </div>
          <p className="text-[13px]">Sin actividad en este período</p>
        </div>
      ) : (
        <div className="relative">
          <div className="flex items-start gap-2 overflow-x-auto pb-2">
            {/* Etiquetas días (col izquierda) */}
            <div className="flex flex-col gap-[3px] pt-5 shrink-0">
              {DOW.map((d) => (
                <div
                  key={d}
                  className="h-5 flex items-center justify-end pr-1 text-[10px] text-muted-foreground tabular-nums"
                  style={{ width: 30 }}
                >
                  {DIA_SEMANA_SHORT[d]}
                </div>
              ))}
            </div>

            <div className="flex-1 min-w-[600px]">
              {/* Etiquetas horas (top) */}
              <div className="flex gap-[3px] mb-1">
                {HOURS.map((h) => (
                  <div
                    key={h}
                    className="flex-1 text-[9px] text-muted-foreground text-center tabular-nums"
                  >
                    {h % 3 === 0 ? `${h}h` : ""}
                  </div>
                ))}
              </div>
              {/* Grid */}
              <div className="flex flex-col gap-[3px]">
                {grid.map((row, dow) => (
                  <div key={dow} className="flex gap-[3px]">
                    {row.map((cell, hour) => {
                      const intensity =
                        maxCantidad > 0 ? cell.cantidad / maxCantidad : 0;
                      // Apple Blue gradient: muted (0) → primary (1)
                      // 0..0.05 = bg-muted, then alpha 0.15..1 of primary
                      const isCold = intensity < 0.04;
                      const opacity = isCold
                        ? 0
                        : 0.18 + Math.pow(intensity, 0.6) * 0.82;
                      return (
                        <div
                          key={hour}
                          onMouseEnter={(e) =>
                            setHover({
                              dow,
                              hour,
                              rect: (
                                e.currentTarget as HTMLDivElement
                              ).getBoundingClientRect(),
                            })
                          }
                          onMouseLeave={() => setHover(null)}
                          className="flex-1 h-5 rounded-[4px] transition-all duration-150 ease-apple bg-muted/60 hover:ring-2 hover:ring-primary/40"
                          style={
                            isCold
                              ? undefined
                              : {
                                  background: `hsl(var(--primary) / ${opacity})`,
                                }
                          }
                          aria-label={`${DIA_SEMANA_LONG[dow]} ${hour}h: ${cell.cantidad} tickets`}
                        />
                      );
                    })}
                  </div>
                ))}
              </div>
              {/* Leyenda */}
              <div className="mt-3 flex items-center justify-end gap-2 text-[10px] text-muted-foreground">
                <span>Menos</span>
                <div className="flex gap-[2px]">
                  {[0.18, 0.4, 0.6, 0.8, 1].map((alpha, i) => (
                    <div
                      key={i}
                      className="h-2.5 w-2.5 rounded-[2px]"
                      style={{
                        background:
                          alpha === 0
                            ? "hsl(var(--muted))"
                            : `hsl(var(--primary) / ${alpha})`,
                      }}
                    />
                  ))}
                </div>
                <span>Más</span>
              </div>
            </div>
          </div>

          {hover && (
            <div
              className="pointer-events-none fixed z-50"
              style={{
                left: hover.rect.left + hover.rect.width / 2,
                top: hover.rect.top - 8,
                transform: "translate(-50%, -100%)",
              }}
            >
              <AppleTooltip
                title={`${DIA_SEMANA_LONG[hover.dow]} · ${hover.hour}h - ${hover.hour + 1}h`}
                rows={[
                  {
                    label: "Tickets",
                    value: formatNumber(grid[hover.dow][hover.hour].cantidad),
                    color: "hsl(var(--primary))",
                  },
                  {
                    label: "Facturado",
                    value: formatARSDetail(grid[hover.dow][hover.hour].total),
                  },
                ]}
              />
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
