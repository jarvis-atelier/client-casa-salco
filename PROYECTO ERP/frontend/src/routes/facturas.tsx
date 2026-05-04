import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Percent,
  Receipt,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";
import { listFacturas, type FacturasQuery } from "@/api/facturas";
import { listSucursales } from "@/api/sucursales";
import type {
  EstadoComprobante,
  Factura,
  TipoComprobante,
} from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FacturaDetailDialog } from "@/components/facturas/factura-detail-dialog";
import {
  comprobanteLabel,
  daysAgoInputValue,
  formatComprobanteNumero,
  formatDateShort,
  formatMoney,
  tipoComprobanteBadgeVariant,
  todayInputValue,
} from "@/components/facturas/format";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

const PER_PAGE = 20;

export const facturasRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/facturas",
  component: FacturasPage,
});

type ChipFilter =
  | "todos"
  | "ticket"
  | "factura_a"
  | "factura_b"
  | "factura_c"
  | "anuladas";

const CHIPS: { id: ChipFilter; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "ticket", label: "Tickets" },
  { id: "factura_a", label: "Factura A" },
  { id: "factura_b", label: "Factura B" },
  { id: "factura_c", label: "Factura C" },
  { id: "anuladas", label: "Anuladas" },
];

function useDebounced<T>(value: T, delay = 300): T {
  const [d, setD] = React.useState(value);
  React.useEffect(() => {
    const id = setTimeout(() => setD(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return d;
}

function FacturasPage() {
  const [chip, setChip] = React.useState<ChipFilter>("todos");
  const [sucursalId, setSucursalId] = React.useState<number | "todas">(
    "todas",
  );
  const [fechaDesde, setFechaDesde] = React.useState<string>(
    daysAgoInputValue(7),
  );
  const [fechaHasta, setFechaHasta] = React.useState<string>(todayInputValue());
  const [busqueda, setBusqueda] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [detailOpen, setDetailOpen] = React.useState(false);

  const debouncedBusqueda = useDebounced(busqueda, 300);

  const { data: sucursales = [] } = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
  });

  // Reset page on filter change
  React.useEffect(() => {
    setPage(1);
  }, [chip, sucursalId, fechaDesde, fechaHasta, debouncedBusqueda]);

  const queryParams: FacturasQuery = React.useMemo(() => {
    const params: FacturasQuery = {
      page,
      per_page: PER_PAGE,
    };
    if (sucursalId !== "todas") params.sucursal_id = sucursalId;
    if (fechaDesde) params.fecha_desde = fechaDesde;
    if (fechaHasta) params.fecha_hasta = fechaHasta;
    if (chip !== "todos" && chip !== "anuladas") {
      params.tipo = chip;
    }
    return params;
  }, [page, sucursalId, fechaDesde, fechaHasta, chip]);

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["facturas", queryParams],
    queryFn: () => listFacturas(queryParams),
    placeholderData: keepPreviousData,
  });

  const items = React.useMemo(() => {
    let list = data?.items ?? [];
    // El backend no tiene un filtro estado=anulada, filtramos client-side.
    if (chip === "anuladas") {
      list = list.filter((f) => f.estado === "anulada");
    }
    if (debouncedBusqueda.trim()) {
      const q = debouncedBusqueda.trim().toLowerCase();
      list = list.filter((f) => {
        const numero = formatComprobanteNumero(
          f.punto_venta,
          f.numero,
        ).toLowerCase();
        return (
          numero.includes(q) ||
          String(f.numero).includes(q) ||
          (f.cae ?? "").toLowerCase().includes(q)
        );
      });
    }
    return list;
  }, [data, chip, debouncedBusqueda]);

  // Resumen con todas las facturas del período (no del page actual)
  const { data: resumenData } = useQuery({
    queryKey: ["facturas-resumen", queryParams],
    queryFn: () =>
      listFacturas({ ...queryParams, page: 1, per_page: 500 }),
    placeholderData: keepPreviousData,
  });

  const resumen = React.useMemo(() => {
    let list = resumenData?.items ?? [];
    if (chip === "anuladas") list = list.filter((f) => f.estado === "anulada");
    let total = 0;
    let iva = 0;
    let count = 0;
    for (const f of list) {
      if (f.estado === "anulada") continue;
      total += parseDecimal(f.total) ?? 0;
      iva += parseDecimal(f.total_iva) ?? 0;
      count += 1;
    }
    return { count, total, iva };
  }, [resumenData, chip]);

  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;
  const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const to = Math.min(page * PER_PAGE, total);

  const sucursalesById = React.useMemo(() => {
    const map = new Map<number, string>();
    sucursales.forEach((s) => map.set(s.id, s.codigo));
    return map;
  }, [sucursales]);

  const openDetail = (id: number) => {
    setSelectedId(id);
    setDetailOpen(true);
  };

  const filtersActive =
    chip !== "todos" ||
    sucursalId !== "todas" ||
    busqueda.trim().length > 0;

  return (
    <div className="flex flex-col gap-7 max-w-[1280px]">
      <div className="flex flex-col gap-1.5">
        <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
          Facturas
        </h2>
        <p className="text-[14px] text-muted-foreground">
          Histórico de comprobantes emitidos. Filtrá por tipo, sucursal o rango
          de fechas, y entrá a una factura para ver el detalle, reimprimir o
          anular.
        </p>
      </div>

      {/* Resumen cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <SummaryCard
          icon={Receipt}
          label="Comprobantes"
          value={String(resumen.count)}
        />
        <SummaryCard
          icon={Wallet}
          label="Total facturado"
          value={formatMoney(resumen.total)}
          tabular
        />
        <SummaryCard
          icon={Percent}
          label="IVA total"
          value={formatMoney(resumen.iva)}
          tabular
          muted
        />
      </div>

      {/* Chips */}
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
      </div>

      {/* Filtros */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
          <div className="md:col-span-3 flex flex-col gap-1">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Sucursal
            </Label>
            <select
              value={sucursalId === "todas" ? "" : String(sucursalId)}
              onChange={(e) =>
                setSucursalId(e.target.value === "" ? "todas" : Number(e.target.value))
              }
              className="h-10 rounded-[8px] border border-border bg-background px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">Todas</option>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.codigo} · {s.nombre}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2 flex flex-col gap-1">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Desde
            </Label>
            <Input
              type="date"
              value={fechaDesde}
              onChange={(e) => setFechaDesde(e.target.value)}
              className="h-10"
            />
          </div>

          <div className="md:col-span-2 flex flex-col gap-1">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Hasta
            </Label>
            <Input
              type="date"
              value={fechaHasta}
              onChange={(e) => setFechaHasta(e.target.value)}
              className="h-10"
            />
          </div>

          <div className="md:col-span-4 flex flex-col gap-1">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Buscar
            </Label>
            <Input
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Número de comprobante o CAE"
              className="h-10"
            />
          </div>

          <div className="md:col-span-1 flex items-end justify-end">
            {filtersActive && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setChip("todos");
                  setSucursalId("todas");
                  setBusqueda("");
                }}
                className="h-10 px-2 text-muted-foreground"
                title="Limpiar filtros"
              >
                <X className="h-4 w-4" strokeWidth={1.5} />
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Tabla */}
      <Card className="overflow-hidden p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[120px]">Fecha</TableHead>
              <TableHead className="w-[80px]">Sucursal</TableHead>
              <TableHead className="w-[110px]">Tipo</TableHead>
              <TableHead className="w-[180px]">Nº comprobante</TableHead>
              <TableHead>Cliente</TableHead>
              <TableHead className="w-[140px] text-right">Total</TableHead>
              <TableHead className="w-[160px]">CAE</TableHead>
              <TableHead className="w-[100px]">Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && items.length === 0
              ? Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                    <TableCell colSpan={8}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : items.map((f) => (
                  <FacturaRow
                    key={f.id}
                    factura={f}
                    sucursalCodigo={
                      sucursalesById.get(f.sucursal_id) ?? `S${f.sucursal_id}`
                    }
                    onClick={() => openDetail(f.id)}
                  />
                ))}

            {!isLoading && items.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={8} className="py-16">
                  <div className="flex flex-col items-center gap-3 text-center">
                    <div className="rounded-full bg-muted/60 p-3">
                      <FileText
                        className="h-6 w-6 text-muted-foreground"
                        strokeWidth={1.5}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <p className="text-[14px] font-medium text-foreground">
                        Sin facturas en este filtro
                      </p>
                      <p className="text-[13px] text-muted-foreground">
                        Probá ajustar la sucursal, el rango de fechas o el tipo.
                      </p>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {isError && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={8} className="py-12 text-center">
                  <p className="text-[13px] text-destructive">
                    No pudimos cargar las facturas.
                  </p>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Paginación */}
      <div className="flex items-center justify-between gap-4">
        <p className="text-[13px] text-muted-foreground tabular-nums">
          {total === 0
            ? "Sin facturas"
            : `Mostrando ${from}-${to} de ${total}`}
          {isFetching && !isLoading && (
            <span className="ml-2 text-muted-foreground/70">
              actualizando…
            </span>
          )}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || isLoading}
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
            disabled={page >= (pages || 1) || isLoading}
          >
            Siguiente
            <ChevronRight strokeWidth={1.5} />
          </Button>
        </div>
      </div>

      <FacturaDetailDialog
        facturaId={selectedId}
        open={detailOpen}
        onOpenChange={(o) => {
          setDetailOpen(o);
          if (!o) setSelectedId(null);
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function SummaryCard({
  icon: Icon,
  label,
  value,
  tabular,
  muted,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tabular?: boolean;
  muted?: boolean;
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
            muted && "text-muted-foreground",
          )}
        >
          {value}
        </span>
      </div>
      <div className="rounded-full bg-muted/60 p-2 mt-0.5">
        <Icon
          className="h-[14px] w-[14px] text-muted-foreground"
          strokeWidth={1.5}
        />
      </div>
    </Card>
  );
}

function FacturaRow({
  factura,
  sucursalCodigo,
  onClick,
}: {
  factura: Factura;
  sucursalCodigo: string;
  onClick: () => void;
}) {
  const numero = formatComprobanteNumero(factura.punto_venta, factura.numero);
  return (
    <TableRow className="cursor-pointer" onClick={onClick}>
      <TableCell className="text-[13px] text-muted-foreground tabular-nums">
        {formatDateShort(factura.fecha)}
      </TableCell>
      <TableCell className="font-mono text-[12px] text-muted-foreground">
        {sucursalCodigo}
      </TableCell>
      <TableCell>
        <Badge variant={tipoComprobanteBadgeVariant(factura.tipo)}>
          {comprobanteLabel(factura.tipo)}
        </Badge>
      </TableCell>
      <TableCell className="font-mono text-[13px]">{numero}</TableCell>
      <TableCell className="text-[13px]">
        {factura.cliente_nombre ? (
          <span className="text-foreground truncate block max-w-[260px]">
            {factura.cliente_nombre}
          </span>
        ) : factura.cliente_id ? (
          <span className="text-foreground">Cliente #{factura.cliente_id}</span>
        ) : (
          <span className="text-muted-foreground">Consumidor Final</span>
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums font-medium">
        {formatMoney(factura.total)}
      </TableCell>
      <TableCell className="font-mono text-[12px] text-muted-foreground">
        {factura.cae ?? "—"}
      </TableCell>
      <TableCell>
        <FacturaEstadoBadge estado={factura.estado} />
      </TableCell>
    </TableRow>
  );
}

function FacturaEstadoBadge({ estado }: { estado: EstadoComprobante }) {
  if (estado === "anulada") return <Badge variant="destructive">Anulada</Badge>;
  if (estado === "emitida") return <Badge variant="success">Emitida</Badge>;
  return <Badge variant="secondary">Borrador</Badge>;
}

// Re-export tipos que usamos solo para que TS detecte cambios en consumidores.
export type { TipoComprobante };
