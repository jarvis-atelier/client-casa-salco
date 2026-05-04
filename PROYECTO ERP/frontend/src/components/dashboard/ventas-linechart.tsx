import * as React from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AppleTooltip } from "./chart-tooltip";
import {
  formatARSCompact,
  formatARSDetail,
  formatDateLong,
  formatDateShort,
  formatNumber,
} from "@/lib/format";
import type { VentasPorDia } from "@/api/reports";

interface ChartRow {
  fecha: string;
  total: number;
  cantidad: number;
}

interface VentasLineChartProps {
  data: VentasPorDia[] | undefined;
  loading: boolean;
}

export function VentasLineChart({ data, loading }: VentasLineChartProps) {
  const rows = React.useMemo<ChartRow[]>(() => {
    return (
      data?.map((d) => ({
        fecha: d.fecha,
        total: parseFloat(d.total) || 0,
        cantidad: d.cantidad,
      })) ?? []
    );
  }, [data]);

  const isEmpty = !loading && rows.length === 0;

  return (
    <Card className="p-6 h-[400px] flex flex-col">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="rounded-[10px] bg-primary/10 p-2 shrink-0">
            <TrendingUp
              className="h-[18px] w-[18px] text-primary"
              strokeWidth={1.5}
            />
          </div>
          <div>
            <h3 className="text-[15px] font-semibold tracking-tight leading-tight">
              Ventas del período
            </h3>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              Total facturado por día
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        {loading ? (
          <Skeleton className="h-full w-full" />
        ) : isEmpty ? (
          <EmptyChart message="Sin actividad en este período" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={rows}
              margin={{ top: 8, right: 12, bottom: 4, left: 0 }}
            >
              <defs>
                <linearGradient id="lineFill" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor="hsl(var(--primary))"
                    stopOpacity={0.2}
                  />
                  <stop
                    offset="100%"
                    stopColor="hsl(var(--primary))"
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="hsl(var(--border))"
                opacity={0.5}
              />
              <XAxis
                dataKey="fecha"
                tickFormatter={formatDateShort}
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={{ stroke: "hsl(var(--border))" }}
                minTickGap={20}
              />
              <YAxis
                tickFormatter={(v) => formatARSCompact(v)}
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={false}
                width={60}
              />
              <Tooltip
                cursor={{
                  stroke: "hsl(var(--primary))",
                  strokeOpacity: 0.2,
                  strokeWidth: 1,
                }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as ChartRow;
                  return (
                    <AppleTooltip
                      title={formatDateLong(d.fecha)}
                      rows={[
                        {
                          label: "Total",
                          value: formatARSDetail(d.total),
                          color: "hsl(var(--primary))",
                        },
                        {
                          label: "Tickets",
                          value: formatNumber(d.cantidad),
                        },
                      ]}
                    />
                  );
                }}
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                dot={false}
                activeDot={{
                  r: 4,
                  fill: "hsl(var(--primary))",
                  stroke: "hsl(var(--background))",
                  strokeWidth: 2,
                }}
                animationDuration={400}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
      <div className="rounded-full bg-muted/60 p-3 mb-3">
        <TrendingUp className="h-5 w-5 opacity-50" strokeWidth={1.5} />
      </div>
      <p className="text-[13px]">{message}</p>
    </div>
  );
}
