import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Package, BarChart3 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AppleTooltip } from "./chart-tooltip";
import { formatARSCompact, formatARSDetail, formatNumber } from "@/lib/format";
import type { TopProducto } from "@/api/reports";
import { cn } from "@/lib/utils";

interface TopProductosChartProps {
  data: TopProducto[] | undefined;
  loading: boolean;
}

type Metric = "cantidad" | "total";

interface Row {
  codigo: string;
  descripcion: string;
  short: string;
  cantidad: number;
  total: number;
}

function shortDesc(s: string, n = 28): string {
  if (s.length <= n) return s;
  return s.slice(0, n - 1) + "…";
}

export function TopProductosChart({ data, loading }: TopProductosChartProps) {
  const [metric, setMetric] = React.useState<Metric>("cantidad");

  const rows = React.useMemo<Row[]>(() => {
    if (!data) return [];
    return data
      .map((d) => ({
        codigo: d.codigo,
        descripcion: d.descripcion,
        short: shortDesc(d.descripcion),
        cantidad: parseFloat(d.cantidad_vendida) || 0,
        total: parseFloat(d.total_facturado) || 0,
      }))
      .sort((a, b) => b[metric] - a[metric]);
  }, [data, metric]);

  const isEmpty = !loading && rows.length === 0;
  const dataKey = metric;

  return (
    <Card className="p-6 h-[480px] flex flex-col">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="rounded-[10px] bg-primary/10 p-2 shrink-0">
            <Package
              className="h-[18px] w-[18px] text-primary"
              strokeWidth={1.5}
            />
          </div>
          <div>
            <h3 className="text-[15px] font-semibold tracking-tight leading-tight">
              Top productos vendidos
            </h3>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              Top 10 del período
            </p>
          </div>
        </div>
        <div className="inline-flex items-center rounded-[8px] border border-border p-0.5 bg-muted/30">
          <button
            type="button"
            onClick={() => setMetric("cantidad")}
            className={cn(
              "px-2.5 py-1 text-[11px] font-medium rounded-[6px] transition-colors",
              metric === "cantidad"
                ? "bg-card text-foreground shadow-apple"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Unidades
          </button>
          <button
            type="button"
            onClick={() => setMetric("total")}
            className={cn(
              "px-2.5 py-1 text-[11px] font-medium rounded-[6px] transition-colors",
              metric === "total"
                ? "bg-card text-foreground shadow-apple"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Facturado
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        {loading ? (
          <Skeleton className="h-full w-full" />
        ) : isEmpty ? (
          <EmptyChart message="Sin productos vendidos en este período" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ top: 4, right: 16, bottom: 4, left: 0 }}
              barSize={16}
            >
              <CartesianGrid
                horizontal={false}
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.5}
              />
              <XAxis
                type="number"
                tickFormatter={(v) =>
                  metric === "total" ? formatARSCompact(v) : formatNumber(v)
                }
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="short"
                width={170}
                tick={{ fontSize: 11, fill: "hsl(var(--foreground))" }}
                tickLine={false}
                axisLine={false}
                interval={0}
              />
              <Tooltip
                cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const r = payload[0].payload as Row;
                  return (
                    <AppleTooltip
                      title={r.descripcion}
                      rows={[
                        {
                          label: "Código",
                          value: r.codigo,
                        },
                        {
                          label: "Unidades",
                          value: formatNumber(r.cantidad),
                          color: "hsl(var(--primary))",
                        },
                        {
                          label: "Facturado",
                          value: formatARSDetail(r.total),
                        },
                      ]}
                    />
                  );
                }}
              />
              <Bar
                dataKey={dataKey}
                fill="hsl(var(--primary))"
                radius={[0, 4, 4, 0]}
                animationDuration={400}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full w-full text-muted-foreground">
      <div className="rounded-full bg-muted/60 p-3 mb-3">
        <BarChart3 className="h-5 w-5 opacity-50" strokeWidth={1.5} />
      </div>
      <p className="text-[13px]">{message}</p>
    </div>
  );
}
