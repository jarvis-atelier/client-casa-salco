import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { DollarSign, Receipt, ShoppingBag, Percent } from "lucide-react";
import { listSucursales } from "@/api/sucursales";
import {
  getMediosPago,
  getTopProductos,
  getVentasPorDia,
  getVentasPorHora,
  getVentasResumen,
} from "@/api/reports";
import { PriceFeedPanel } from "@/components/dashboard/price-feed-panel";
import {
  DashboardFilters,
  resolvePreset,
  type DashboardRange,
} from "@/components/dashboard/dashboard-filters";
import { StatCard } from "@/components/dashboard/stat-card";
import { VentasLineChart } from "@/components/dashboard/ventas-linechart";
import { SucursalDonut } from "@/components/dashboard/sucursal-donut";
import { TopProductosChart } from "@/components/dashboard/top-productos-chart";
import { MediosPagoDonut } from "@/components/dashboard/medios-pago-donut";
import { HorasHeatmap } from "@/components/dashboard/horas-heatmap";
import { CorrelacionesCard } from "@/components/dashboard/correlaciones-card";
import { ReposicionCard } from "@/components/stock/reposicion-card";
import { formatARS, formatNumber } from "@/lib/format";
import { appLayoutRoute } from "./app-layout";

export const dashboardRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/",
  component: DashboardPage,
});

function DashboardPage() {
  const [range, setRange] = React.useState<DashboardRange>(() =>
    resolvePreset("ultimos_30_dias"),
  );
  const [sucursalId, setSucursalId] = React.useState<number | null>(null);

  const sucursalesQ = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
  });

  const baseParams = React.useMemo(
    () => ({
      fecha_desde: range.fecha_desde,
      fecha_hasta: range.fecha_hasta,
      ...(sucursalId ? { sucursal_id: sucursalId } : {}),
    }),
    [range, sucursalId],
  );

  const resumenQ = useQuery({
    queryKey: ["report-resumen", baseParams],
    queryFn: () => getVentasResumen(baseParams),
  });

  const ventasDiaQ = useQuery({
    queryKey: ["report-ventas-dia", baseParams],
    queryFn: () => getVentasPorDia(baseParams),
  });

  const topProdQ = useQuery({
    queryKey: ["report-top-prod", baseParams],
    queryFn: () => getTopProductos({ ...baseParams, limit: 10 }),
  });

  const horasQ = useQuery({
    queryKey: ["report-horas", baseParams],
    queryFn: () => getVentasPorHora(baseParams),
  });

  const mediosQ = useQuery({
    queryKey: ["report-medios", baseParams],
    queryFn: () => getMediosPago(baseParams),
  });

  const ticketPromedio = React.useMemo(() => {
    if (!resumenQ.data) return null;
    return parseFloat(resumenQ.data.ticket_promedio);
  }, [resumenQ.data]);

  return (
    <div className="flex flex-col gap-6 max-w-[1400px]">
      {/* Header con filtros sticky-feel */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Dashboard
          </h2>
          <p className="mt-1 text-[14px] text-muted-foreground">
            Panorama general de tu operación multi-sucursal.
          </p>
        </div>
        <DashboardFilters
          range={range}
          onRangeChange={setRange}
          sucursalId={sucursalId}
          onSucursalChange={setSucursalId}
          sucursales={sucursalesQ.data}
        />
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Ventas del período"
          value={formatARS(resumenQ.data?.total_facturado ?? null)}
          icon={DollarSign}
          variation={resumenQ.data?.var_total_pct ?? null}
          loading={resumenQ.isLoading}
        />
        <StatCard
          label="Tickets"
          value={formatNumber(resumenQ.data?.total_facturas ?? null)}
          icon={Receipt}
          variation={resumenQ.data?.var_cantidad_pct ?? null}
          loading={resumenQ.isLoading}
        />
        <StatCard
          label="Ticket promedio"
          value={formatARS(ticketPromedio)}
          icon={ShoppingBag}
          variation={resumenQ.data?.var_ticket_pct ?? null}
          loading={resumenQ.isLoading}
        />
        <StatCard
          label="IVA del período"
          value={formatARS(resumenQ.data?.total_iva ?? null)}
          icon={Percent}
          variation={resumenQ.data?.var_iva_pct ?? null}
          loading={resumenQ.isLoading}
        />
      </div>

      {/* Stock inteligente — accent: reposición sugerida */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <ReposicionCard sucursalId={sucursalId} />
      </div>

      {/* Línea + donut sucursales */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <VentasLineChart
            data={ventasDiaQ.data}
            loading={ventasDiaQ.isLoading}
          />
        </div>
        <div className="lg:col-span-1">
          <SucursalDonut
            data={resumenQ.data?.por_sucursal}
            loading={resumenQ.isLoading}
          />
        </div>
      </div>

      {/* Top productos + medios de pago */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <TopProductosChart
            data={topProdQ.data}
            loading={topProdQ.isLoading}
          />
        </div>
        <div className="lg:col-span-1">
          <MediosPagoDonut data={mediosQ.data} loading={mediosQ.isLoading} />
        </div>
      </div>

      {/* Heatmap horas pico */}
      <HorasHeatmap data={horasQ.data} loading={horasQ.isLoading} />

      {/* Correlaciones de productos (Apriori / market basket) */}
      <CorrelacionesCard sucursalId={sucursalId} />

      {/* Sync de precios en vivo (preexistente) */}
      <PriceFeedPanel />
    </div>
  );
}
