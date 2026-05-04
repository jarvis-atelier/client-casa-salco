import * as React from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Store as StoreIcon, PieChart as PieIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AppleTooltip } from "./chart-tooltip";
import { formatARSDetail, formatNumber } from "@/lib/format";
import type { VentasResumenSucursal } from "@/api/reports";

interface SucursalDonutProps {
  data: VentasResumenSucursal[] | undefined;
  loading: boolean;
}

// Paleta Apple-like: Apple Blue + variantes neutras (azules, grises, slate).
// Suficiente para 4-6 sucursales.
const APPLE_PALETTE = [
  "hsl(211 100% 50%)", // Apple Blue
  "hsl(211 70% 65%)", // azul más claro
  "hsl(220 15% 45%)", // slate medio
  "hsl(211 90% 35%)", // azul oscuro
  "hsl(220 10% 60%)", // gris cálido
  "hsl(200 50% 55%)", // azul cyan
];

interface PieRow {
  name: string;
  codigo: string;
  total: number;
  cantidad: number;
  color: string;
}

export function SucursalDonut({ data, loading }: SucursalDonutProps) {
  const rows = React.useMemo<PieRow[]>(() => {
    return (
      data?.map((d, i) => ({
        name: d.nombre,
        codigo: d.codigo,
        total: parseFloat(d.total) || 0,
        cantidad: d.cantidad,
        color: APPLE_PALETTE[i % APPLE_PALETTE.length],
      })) ?? []
    );
  }, [data]);

  const totalSum = rows.reduce((acc, r) => acc + r.total, 0);
  const isEmpty = !loading && rows.length === 0;

  return (
    <Card className="p-6 h-[400px] flex flex-col">
      <div className="flex items-center gap-3 mb-2">
        <div className="rounded-[10px] bg-primary/10 p-2 shrink-0">
          <StoreIcon
            className="h-[18px] w-[18px] text-primary"
            strokeWidth={1.5}
          />
        </div>
        <div>
          <h3 className="text-[15px] font-semibold tracking-tight leading-tight">
            Por sucursal
          </h3>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            Distribución de ventas
          </p>
        </div>
      </div>

      <div className="flex-1 min-h-0 flex items-center">
        {loading ? (
          <Skeleton className="h-full w-full" />
        ) : isEmpty ? (
          <EmptyChart message="Sin actividad en este período" />
        ) : (
          <div className="grid grid-cols-2 gap-3 w-full h-full items-center">
            <div className="h-full min-h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={rows}
                    dataKey="total"
                    nameKey="codigo"
                    cx="50%"
                    cy="50%"
                    innerRadius="62%"
                    outerRadius="92%"
                    paddingAngle={2}
                    stroke="hsl(var(--card))"
                    strokeWidth={2}
                    animationDuration={400}
                  >
                    {rows.map((row, i) => (
                      <Cell key={i} fill={row.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const r = payload[0].payload as PieRow;
                      const pct = totalSum
                        ? (r.total / totalSum) * 100
                        : 0;
                      return (
                        <AppleTooltip
                          title={r.name}
                          rows={[
                            {
                              label: "Total",
                              value: formatARSDetail(r.total),
                              color: r.color,
                            },
                            {
                              label: "Tickets",
                              value: formatNumber(r.cantidad),
                            },
                            {
                              label: "Participación",
                              value: `${pct.toFixed(1)}%`,
                            },
                          ]}
                        />
                      );
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-col gap-2 min-w-0">
              {rows.map((r) => {
                const pct = totalSum ? (r.total / totalSum) * 100 : 0;
                return (
                  <div
                    key={r.codigo}
                    className="flex items-start gap-2 min-w-0"
                  >
                    <span
                      className="mt-1 inline-block h-2.5 w-2.5 rounded-sm shrink-0"
                      style={{ background: r.color }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-[12px] font-medium text-foreground truncate">
                          {r.codigo}
                        </span>
                        <span className="text-[12px] tabular-nums text-foreground font-medium">
                          {pct.toFixed(0)}%
                        </span>
                      </div>
                      <div className="text-[11px] text-muted-foreground tabular-nums truncate">
                        {formatARSDetail(r.total)}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full w-full text-muted-foreground">
      <div className="rounded-full bg-muted/60 p-3 mb-3">
        <PieIcon className="h-5 w-5 opacity-50" strokeWidth={1.5} />
      </div>
      <p className="text-[13px]">{message}</p>
    </div>
  );
}
