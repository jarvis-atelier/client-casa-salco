import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Wallet, X } from "lucide-react";
import {
  calcularArqueo,
  isMovimientoEgreso,
  listMovimientos,
  type MovimientosQuery,
} from "@/api/movimientos";
import { listSucursales } from "@/api/sucursales";
import type {
  MedioPago,
  MovimientoCaja,
  TipoMovimiento,
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
import { ArqueoSidebar } from "@/components/movimientos/arqueo-sidebar";
import {
  formatMoney,
  formatTimeShort,
  medioPagoLabel,
  todayInputValue,
} from "@/components/facturas/format";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

const PER_PAGE = 50;

export const movimientosRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/movimientos",
  component: MovimientosPage,
});

type ChipFilter =
  | "todos"
  | "venta"
  | "cobranza"
  | "pago_proveedor"
  | "apertura_caja"
  | "cierre_caja"
  | "ajuste"
  | "cheque";

const CHIPS: { id: ChipFilter; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "venta", label: "Ventas" },
  { id: "cobranza", label: "Cobranzas" },
  { id: "pago_proveedor", label: "Pagos" },
  { id: "apertura_caja", label: "Apertura" },
  { id: "cierre_caja", label: "Cierre" },
  { id: "ajuste", label: "Ajustes" },
  { id: "cheque", label: "Cheques" },
];

const TIPO_LABEL: Record<TipoMovimiento, string> = {
  venta: "Venta",
  devolucion: "Devolución",
  cobranza: "Cobranza",
  pago_proveedor: "Pago",
  apertura_caja: "Apertura",
  cierre_caja: "Cierre",
  ingreso_efectivo: "Ingreso",
  egreso_efectivo: "Egreso",
  ajuste: "Ajuste",
  cheque_recibido: "Cheque +",
  cheque_entregado: "Cheque −",
};

function tipoBadgeVariant(
  tipo: TipoMovimiento,
):
  | "default"
  | "secondary"
  | "destructive"
  | "success"
  | "outline" {
  if (tipo === "venta" || tipo === "cobranza" || tipo === "ingreso_efectivo")
    return "success";
  if (
    tipo === "devolucion" ||
    tipo === "egreso_efectivo" ||
    tipo === "pago_proveedor" ||
    tipo === "cheque_entregado"
  )
    return "destructive";
  if (tipo === "apertura_caja" || tipo === "cierre_caja") return "default";
  return "secondary";
}

function MovimientosPage() {
  const [chip, setChip] = React.useState<ChipFilter>("todos");
  const [sucursalId, setSucursalId] = React.useState<number | "todas">(
    "todas",
  );
  const [fecha, setFecha] = React.useState<string>(todayInputValue());
  const [cajaNumero, setCajaNumero] = React.useState<number>(1);
  const [page, setPage] = React.useState(1);

  const { data: sucursales = [] } = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
  });

  const sucursalNombre = React.useMemo(() => {
    if (sucursalId === "todas") return null;
    const s = sucursales.find((s) => s.id === sucursalId);
    return s ? `${s.codigo} · ${s.nombre}` : null;
  }, [sucursalId, sucursales]);

  React.useEffect(() => {
    setPage(1);
  }, [chip, sucursalId, fecha, cajaNumero]);

  const queryParams: MovimientosQuery = React.useMemo(() => {
    const params: MovimientosQuery = {
      page,
      per_page: PER_PAGE,
      caja_numero: cajaNumero,
      fecha_desde: fecha,
      fecha_hasta: fecha,
    };
    if (sucursalId !== "todas") params.sucursal_id = sucursalId;
    if (chip === "cheque") {
      // El backend no soporta OR sobre tipos, así que dejamos sin filtro tipo y
      // filtramos client-side abajo.
    } else if (chip !== "todos") {
      params.tipo = chip as TipoMovimiento;
    }
    return params;
  }, [page, sucursalId, fecha, cajaNumero, chip]);

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["movimientos", queryParams],
    queryFn: () => listMovimientos(queryParams),
    placeholderData: keepPreviousData,
  });

  // Para el arqueo del día, traemos TODOS los movimientos (sin paginar) sin filtro de tipo
  // — necesitamos sumas completas independientes del filtro de chip.
  const { data: arqueoData } = useQuery({
    queryKey: [
      "movimientos-arqueo",
      sucursalId,
      fecha,
      cajaNumero,
    ],
    queryFn: () =>
      listMovimientos({
        sucursal_id: sucursalId === "todas" ? undefined : sucursalId,
        fecha_desde: fecha,
        fecha_hasta: fecha,
        caja_numero: cajaNumero,
        per_page: 500,
      }),
    placeholderData: keepPreviousData,
  });

  const arqueo = React.useMemo(
    () =>
      calcularArqueo(
        (arqueoData?.items ?? []).filter((m) => m.caja_numero === cajaNumero),
      ),
    [arqueoData, cajaNumero],
  );

  const filteredItems = React.useMemo(() => {
    let list = data?.items ?? [];
    // El backend hoy NO filtra por caja_numero — filtramos client-side.
    list = list.filter((m) => m.caja_numero === cajaNumero);
    if (chip === "cheque") {
      list = list.filter(
        (m) =>
          m.tipo === "cheque_recibido" || m.tipo === "cheque_entregado",
      );
    }
    return list;
  }, [data, chip, cajaNumero]);

  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;
  const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const to = Math.min(page * PER_PAGE, total);

  const filtersActive =
    chip !== "todos" || sucursalId !== "todas" || cajaNumero !== 1;

  // Print arqueo: vista print-friendly imprimible con Ctrl+P.
  // Para MVP usamos window.print() sobre la propia pantalla con clase print-only en el sidebar.
  const handlePrintArqueo = () => {
    // Marcamos un atributo en <html> para activar reglas CSS de impresión definidas inline acá.
    const html = document.documentElement;
    html.setAttribute("data-printing", "arqueo");
    setTimeout(() => {
      window.print();
      // Tras imprimir limpiamos el flag.
      setTimeout(() => html.removeAttribute("data-printing"), 200);
    }, 50);
  };

  return (
    <div className="flex flex-col gap-7 max-w-[1440px]">
      <style>{PRINT_STYLES}</style>

      <div className="flex flex-col gap-1.5 print:hidden">
        <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
          Movimientos de caja
        </h2>
        <p className="text-[14px] text-muted-foreground">
          Ledger universal: todas las operaciones financieras del día. Filtrá
          por tipo, sucursal o caja, y mirá el arqueo en vivo a la derecha.
        </p>
      </div>

      {/* Chips */}
      <div className="flex flex-wrap items-center gap-1.5 print:hidden">
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
      <Card className="p-4 print:hidden">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
          <div className="md:col-span-4 flex flex-col gap-1">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Sucursal
            </Label>
            <select
              value={sucursalId === "todas" ? "" : String(sucursalId)}
              onChange={(e) =>
                setSucursalId(
                  e.target.value === "" ? "todas" : Number(e.target.value),
                )
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
              Caja Nº
            </Label>
            <Input
              type="number"
              min={1}
              value={cajaNumero}
              onChange={(e) =>
                setCajaNumero(Math.max(1, Number(e.target.value) || 1))
              }
              className="h-10 tabular-nums"
            />
          </div>

          <div className="md:col-span-3 flex flex-col gap-1">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Fecha
            </Label>
            <Input
              type="date"
              value={fecha}
              onChange={(e) => setFecha(e.target.value)}
              className="h-10"
            />
          </div>

          <div className="md:col-span-3 flex items-end justify-end">
            {filtersActive && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setChip("todos");
                  setSucursalId("todas");
                  setCajaNumero(1);
                }}
                className="h-10 text-muted-foreground"
              >
                <X className="h-4 w-4" strokeWidth={1.5} />
                Limpiar
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Layout principal: tabla + sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <div className="flex flex-col gap-4 min-w-0">
          <Card className="overflow-hidden p-0">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[64px]">Hora</TableHead>
                  <TableHead className="w-[110px]">Tipo</TableHead>
                  <TableHead className="w-[130px]">Medio</TableHead>
                  <TableHead>Descripción</TableHead>
                  <TableHead className="w-[140px]">Referencia</TableHead>
                  <TableHead className="w-[140px] text-right">Monto</TableHead>
                  <TableHead className="w-[80px]">User</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading && filteredItems.length === 0
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <TableRow
                        key={`sk-${i}`}
                        className="hover:bg-transparent"
                      >
                        <TableCell colSpan={7}>
                          <Skeleton className="h-5 w-full" />
                        </TableCell>
                      </TableRow>
                    ))
                  : filteredItems.map((m) => (
                      <MovimientoRow key={m.id} movimiento={m} />
                    ))}

                {!isLoading && filteredItems.length === 0 && (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={7} className="py-16">
                      <div className="flex flex-col items-center gap-3 text-center">
                        <div className="rounded-full bg-muted/60 p-3">
                          <Wallet
                            className="h-6 w-6 text-muted-foreground"
                            strokeWidth={1.5}
                          />
                        </div>
                        <div className="flex flex-col gap-1">
                          <p className="text-[14px] font-medium text-foreground">
                            Sin movimientos en este filtro
                          </p>
                          <p className="text-[13px] text-muted-foreground">
                            Probá cambiar la fecha o seleccionar otra caja.
                          </p>
                        </div>
                      </div>
                    </TableCell>
                  </TableRow>
                )}

                {isError && (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={7} className="py-12 text-center">
                      <p className="text-[13px] text-destructive">
                        No pudimos cargar los movimientos.
                      </p>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>

          <div className="flex items-center justify-between gap-4 print:hidden">
            <p className="text-[13px] text-muted-foreground tabular-nums">
              {total === 0
                ? "Sin movimientos"
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
        </div>

        <div>
          <ArqueoSidebar
            totales={arqueo}
            fechaCaja={fecha}
            cajaNumero={cajaNumero}
            sucursalNombre={sucursalNombre}
            onPrint={handlePrintArqueo}
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Print styles
// ---------------------------------------------------------------------------

/**
 * MVP de impresión de arqueo: ocultamos todo y mostramos sólo el sidebar
 * cuando `data-printing="arqueo"` está en el <html>. El user imprime con Ctrl+P
 * o el botón "Imprimir arqueo" que dispara window.print().
 */
const PRINT_STYLES = `
@media print {
  html[data-printing="arqueo"] body * { visibility: hidden; }
  html[data-printing="arqueo"] [data-print-target="arqueo"],
  html[data-printing="arqueo"] [data-print-target="arqueo"] * { visibility: visible; }
  html[data-printing="arqueo"] [data-print-target="arqueo"] {
    position: absolute; left: 0; top: 0; width: 100%;
  }
}
`;

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

function MovimientoRow({ movimiento }: { movimiento: MovimientoCaja }) {
  const monto = parseDecimal(movimiento.monto) ?? 0;
  const egreso = isMovimientoEgreso(movimiento.tipo);
  const signedMonto = egreso ? -Math.abs(monto) : monto;

  return (
    <TableRow className="hover:bg-muted/30">
      <TableCell className="text-[12px] text-muted-foreground tabular-nums font-mono">
        {formatTimeShort(movimiento.fecha)}
      </TableCell>
      <TableCell>
        <Badge variant={tipoBadgeVariant(movimiento.tipo)}>
          {TIPO_LABEL[movimiento.tipo]}
        </Badge>
      </TableCell>
      <TableCell>
        {movimiento.medio ? (
          <Badge variant="outline" className="font-mono lowercase">
            {medioPagoLabel(movimiento.medio as MedioPago)}
          </Badge>
        ) : (
          <span className="text-[12px] text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-[13px] truncate max-w-[280px]">
        {movimiento.descripcion || "—"}
      </TableCell>
      <TableCell className="text-[12px] text-muted-foreground">
        {movimiento.factura_id ? `Factura #${movimiento.factura_id}` : null}
        {movimiento.cliente_id ? `Cliente #${movimiento.cliente_id}` : null}
        {movimiento.proveedor_id
          ? `Proveedor #${movimiento.proveedor_id}`
          : null}
        {!movimiento.factura_id &&
          !movimiento.cliente_id &&
          !movimiento.proveedor_id &&
          "—"}
      </TableCell>
      <TableCell
        className={cn(
          "text-right tabular-nums font-medium",
          egreso ? "text-destructive" : "text-emerald-600 dark:text-emerald-400",
        )}
      >
        {egreso ? "−" : ""}
        {formatMoney(Math.abs(signedMonto))}
      </TableCell>
      <TableCell className="text-[12px] text-muted-foreground">
        {movimiento.user_id ? `#${movimiento.user_id}` : "—"}
      </TableCell>
    </TableRow>
  );
}
