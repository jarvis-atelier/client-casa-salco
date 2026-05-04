import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import {
  AlertTriangle,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Plus,
  Sparkles,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  autoGenerarCompromisos,
  getCompromisosCalendar,
  getCompromisosResumen,
  listCompromisos,
  type CompromisosQuery,
} from "@/api/calendario-pagos";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CalendarView } from "@/components/pagos/calendar-view";
import { CompromisoDetailDialog } from "@/components/pagos/compromiso-detail-dialog";
import { DayDrawer } from "@/components/pagos/day-drawer";
import { NuevoCompromisoDialog } from "@/components/pagos/nuevo-compromiso-dialog";
import {
  diasHasta,
  diasLabel,
  estadoCompromisoBadgeVariant,
  estadoCompromisoLabel,
  formatFechaCompacta,
  tipoCompromisoBadgeVariant,
  tipoCompromisoLabel,
} from "@/components/pagos/format";
import { formatMoney } from "@/components/facturas/format";
import { useToast } from "@/hooks/use-toast";
import type {
  CompromisoPago,
  EstadoCompromiso,
  TipoCompromiso,
} from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

const PER_PAGE = 25;

export const pagosRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/pagos",
  component: PagosPage,
});

type ChipFilter =
  | "todos"
  | "vencidos"
  | "esta_semana"
  | "este_mes"
  | "pendientes"
  | "pagados";

const CHIPS: { id: ChipFilter; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "vencidos", label: "Vencidos" },
  { id: "esta_semana", label: "Esta semana" },
  { id: "este_mes", label: "Este mes" },
  { id: "pendientes", label: "Pendientes" },
  { id: "pagados", label: "Pagados" },
];

type ViewMode = "calendario" | "lista";

function isoToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(
    2,
    "0",
  )}-${String(d.getDate()).padStart(2, "0")}`;
}

function isoOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(
    2,
    "0",
  )}-${String(d.getDate()).padStart(2, "0")}`;
}

function PagosPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const today = new Date();
  const [view, setView] = React.useState<ViewMode>("calendario");
  const [chip, setChip] = React.useState<ChipFilter>("todos");
  const [tipo, setTipo] = React.useState<TipoCompromiso | "todos">("todos");
  const [page, setPage] = React.useState(1);
  const [calAnio, setCalAnio] = React.useState(today.getFullYear());
  const [calMes, setCalMes] = React.useState(today.getMonth() + 1);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerFecha, setDrawerFecha] = React.useState<string | null>(null);
  const [drawerIds, setDrawerIds] = React.useState<number[]>([]);

  const [detailOpen, setDetailOpen] = React.useState(false);
  const [detailId, setDetailId] = React.useState<number | null>(null);

  const [nuevoOpen, setNuevoOpen] = React.useState(false);

  // Resumen
  const { data: resumen } = useQuery({
    queryKey: ["compromisos-resumen"],
    queryFn: getCompromisosResumen,
    refetchOnWindowFocus: false,
  });

  // Calendario
  const mesParam = `${calAnio}-${String(calMes).padStart(2, "0")}`;
  const { data: calData, isLoading: calLoading } = useQuery({
    queryKey: ["compromisos-calendar", mesParam],
    queryFn: () => getCompromisosCalendar(mesParam),
    enabled: view === "calendario",
    placeholderData: keepPreviousData,
  });

  // Listado
  const queryParams: CompromisosQuery = React.useMemo(() => {
    const p: CompromisosQuery = { page, per_page: PER_PAGE };
    if (tipo !== "todos") p.tipo = tipo;

    if (chip === "vencidos") {
      p.fecha_hasta = isoOffset(-1);
      p.estado = "vencido";
    } else if (chip === "esta_semana") {
      p.fecha_desde = isoToday();
      p.fecha_hasta = isoOffset(7);
    } else if (chip === "este_mes") {
      p.fecha_desde = isoToday();
      p.fecha_hasta = isoOffset(30);
    } else if (chip === "pendientes") {
      p.estado = "pendiente";
    } else if (chip === "pagados") {
      p.estado = "pagado";
    }
    return p;
  }, [page, chip, tipo]);

  React.useEffect(() => setPage(1), [chip, tipo]);

  const { data: lista, isLoading: listaLoading } = useQuery({
    queryKey: ["compromisos", queryParams],
    queryFn: () => listCompromisos(queryParams),
    placeholderData: keepPreviousData,
    enabled: view === "lista",
  });

  // Auto-generar
  const autoGenMutation = useMutation({
    mutationFn: () => autoGenerarCompromisos(),
    onSuccess: (res) => {
      toast({
        title: "Compromisos auto-generados",
        description: `${res.creados} compromisos creados (${res.desde_facturas} de facturas, ${res.desde_tarjetas} de tarjetas).`,
      });
      queryClient.invalidateQueries({ queryKey: ["compromisos"] });
      queryClient.invalidateQueries({ queryKey: ["compromisos-resumen"] });
      queryClient.invalidateQueries({ queryKey: ["compromisos-calendar"] });
    },
    onError: (err) => {
      const msg =
        (err as AxiosError<{ error?: string }>).response?.data?.error ??
        "Error al auto-generar.";
      toast({ variant: "destructive", title: "Error", description: msg });
    },
  });

  const openCompromiso = (id: number) => {
    setDetailId(id);
    setDetailOpen(true);
  };

  const onDayClick = (fecha: string, ids: number[]) => {
    setDrawerFecha(fecha);
    setDrawerIds(ids);
    setDrawerOpen(true);
  };

  const items = lista?.items ?? [];
  const total = lista?.total ?? 0;
  const pages = lista?.pages ?? 1;
  const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const to = Math.min(page * PER_PAGE, total);

  return (
    <div className="flex flex-col gap-7 max-w-[1280px]">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Calendario de pagos
          </h2>
          <p className="text-[14px] text-muted-foreground">
            Vencimientos de facturas de compras, cuentas corrientes con
            proveedores y resúmenes de tarjetas corporativas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => autoGenMutation.mutate()}
            disabled={autoGenMutation.isPending}
          >
            {autoGenMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" strokeWidth={1.5} />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" strokeWidth={1.5} />
            )}
            Auto-generar
          </Button>
          <Button size="sm" onClick={() => setNuevoOpen(true)}>
            <Plus className="mr-1 h-4 w-4" strokeWidth={1.5} />
            Nuevo compromiso
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          icon={AlertTriangle}
          label="Vencidos"
          value={String(resumen?.vencidos ?? 0)}
          tone="destructive"
        />
        <StatCard
          icon={CalendarClock}
          label="Vence esta semana"
          value={String(resumen?.esta_semana ?? 0)}
          tone="warning"
        />
        <StatCard
          icon={CalendarRange}
          label="Vence este mes"
          value={String(resumen?.este_mes ?? 0)}
        />
        <StatCard
          icon={Wallet}
          label="Total pendiente"
          value={formatMoney(resumen?.total_pendiente)}
          tabular
        />
      </div>

      {/* Toggle vista */}
      <div className="flex items-center justify-between gap-3">
        <div className="inline-flex rounded-full border border-border bg-card p-0.5">
          <button
            onClick={() => setView("calendario")}
            className={cn(
              "px-4 py-1.5 text-[12px] font-medium rounded-full transition-colors duration-200 ease-apple",
              view === "calendario"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Calendario
          </button>
          <button
            onClick={() => setView("lista")}
            className={cn(
              "px-4 py-1.5 text-[12px] font-medium rounded-full transition-colors duration-200 ease-apple",
              view === "lista"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Lista
          </button>
        </div>

        {view === "lista" && (
          <div className="flex items-center gap-2">
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TipoCompromiso | "todos")}
              className="h-8 rounded-[8px] border border-border bg-background px-2 text-[12px] focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="todos">Todos los tipos</option>
              {(
                [
                  "factura_compra",
                  "cuenta_corriente_proveedor",
                  "tarjeta_corporativa",
                  "servicio",
                  "impuesto",
                  "otro",
                ] as TipoCompromiso[]
              ).map((t) => (
                <option key={t} value={t}>
                  {tipoCompromisoLabel(t)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Vista calendario */}
      {view === "calendario" && (
        <CalendarView
          anio={calAnio}
          mes={calMes}
          onMonthChange={(a, m) => {
            setCalAnio(a);
            setCalMes(m);
          }}
          days={calData?.items ?? []}
          isLoading={calLoading}
          onDayClick={onDayClick}
        />
      )}

      {/* Vista lista */}
      {view === "lista" && (
        <>
          <div className="flex flex-wrap items-center gap-1.5">
            {CHIPS.map((c) => {
              const active = chip === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setChip(c.id)}
                  className={cn(
                    "h-8 rounded-full border px-3 text-[12px] font-medium transition-colors duration-200 ease-apple",
                    active
                      ? "border-foreground/15 bg-foreground text-background"
                      : "border-border bg-background text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                  )}
                >
                  {c.label}
                </button>
              );
            })}
            {(chip !== "todos" || tipo !== "todos") && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setChip("todos");
                  setTipo("todos");
                }}
                className="h-8 px-2 text-muted-foreground"
              >
                <X className="h-4 w-4" strokeWidth={1.5} />
              </Button>
            )}
          </div>

          <Card className="overflow-hidden p-0">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[110px]">Vence</TableHead>
                  <TableHead className="w-[120px]">Tipo</TableHead>
                  <TableHead>Descripción</TableHead>
                  <TableHead className="w-[140px] text-right">Total</TableHead>
                  <TableHead className="w-[140px] text-right">Pendiente</TableHead>
                  <TableHead className="w-[100px]">Estado</TableHead>
                  <TableHead className="w-[100px]">Días</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {listaLoading && items.length === 0
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                        <TableCell colSpan={7}>
                          <Skeleton className="h-5 w-full" />
                        </TableCell>
                      </TableRow>
                    ))
                  : items.map((c) => (
                      <CompromisoRow
                        key={c.id}
                        compromiso={c}
                        onClick={() => openCompromiso(c.id)}
                      />
                    ))}

                {!listaLoading && items.length === 0 && (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={7} className="py-16">
                      <div className="flex flex-col items-center gap-3 text-center">
                        <div className="rounded-full bg-muted/60 p-3">
                          <CalendarDays
                            className="h-6 w-6 text-muted-foreground"
                            strokeWidth={1.5}
                          />
                        </div>
                        <p className="text-[14px] font-medium">
                          Sin compromisos en este filtro
                        </p>
                        <p className="text-[13px] text-muted-foreground">
                          Probá cambiar el filtro o crear uno nuevo.
                        </p>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>

          <div className="flex items-center justify-between gap-4">
            <p className="text-[13px] text-muted-foreground tabular-nums">
              {total === 0 ? "Sin compromisos" : `Mostrando ${from}-${to} de ${total}`}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || listaLoading}
              >
                <ChevronLeft strokeWidth={1.5} />
                Anterior
              </Button>
              <span className="text-[13px] tabular-nums text-muted-foreground min-w-[64px] text-center">
                {page} / {pages || 1}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(pages || 1, p + 1))}
                disabled={page >= (pages || 1) || listaLoading}
              >
                Siguiente
                <ChevronRight strokeWidth={1.5} />
              </Button>
            </div>
          </div>
        </>
      )}

      <DayDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        fecha={drawerFecha}
        ids={drawerIds}
        onSelectCompromiso={(id) => {
          setDrawerOpen(false);
          openCompromiso(id);
        }}
      />

      <CompromisoDetailDialog
        compromisoId={detailId}
        open={detailOpen}
        onOpenChange={(o) => {
          setDetailOpen(o);
          if (!o) setDetailId(null);
        }}
      />

      <NuevoCompromisoDialog
        open={nuevoOpen}
        onOpenChange={setNuevoOpen}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function StatCard({
  icon: Icon,
  label,
  value,
  tabular,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tabular?: boolean;
  tone?: "destructive" | "warning";
}) {
  return (
    <Card className="p-4 flex items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span
          className={cn(
            "text-[22px] font-semibold tracking-tight",
            tabular && "tabular-nums",
            tone === "destructive" && "text-rose-500",
            tone === "warning" && "text-amber-500",
          )}
        >
          {value}
        </span>
      </div>
      <div
        className={cn(
          "rounded-full p-2 mt-0.5",
          tone === "destructive"
            ? "bg-rose-500/10"
            : tone === "warning"
              ? "bg-amber-500/10"
              : "bg-muted/60",
        )}
      >
        <Icon
          className={cn(
            "h-[14px] w-[14px]",
            tone === "destructive"
              ? "text-rose-500"
              : tone === "warning"
                ? "text-amber-500"
                : "text-muted-foreground",
          )}
          strokeWidth={1.5}
        />
      </div>
    </Card>
  );
}

function CompromisoRow({
  compromiso,
  onClick,
}: {
  compromiso: CompromisoPago;
  onClick: () => void;
}) {
  const dias = diasHasta(compromiso.fecha_vencimiento);
  const pendiente =
    Number(parseDecimal(compromiso.monto_total) ?? 0) -
    Number(parseDecimal(compromiso.monto_pagado) ?? 0);
  const diasTone =
    dias < 0
      ? "text-rose-500"
      : dias <= 3
        ? "text-amber-500"
        : "text-muted-foreground";

  return (
    <TableRow className="cursor-pointer" onClick={onClick}>
      <TableCell className="text-[13px] tabular-nums">
        {formatFechaCompacta(compromiso.fecha_vencimiento)}
      </TableCell>
      <TableCell>
        <Badge variant={tipoCompromisoBadgeVariant(compromiso.tipo)}>
          {tipoCompromisoLabel(compromiso.tipo)}
        </Badge>
      </TableCell>
      <TableCell className="text-[13px]">
        <span className="text-foreground truncate block max-w-[440px]">
          {compromiso.descripcion}
        </span>
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatMoney(compromiso.monto_total)}
      </TableCell>
      <TableCell className="text-right tabular-nums font-medium">
        {formatMoney(pendiente)}
      </TableCell>
      <TableCell>
        <Badge variant={estadoCompromisoBadgeVariant(compromiso.estado)}>
          {estadoCompromisoLabel(compromiso.estado)}
        </Badge>
      </TableCell>
      <TableCell className={cn("text-[12px]", diasTone)}>
        {compromiso.estado === "pagado" ? "—" : diasLabel(dias)}
      </TableCell>
    </TableRow>
  );
}

export type { TipoCompromiso, EstadoCompromiso };
