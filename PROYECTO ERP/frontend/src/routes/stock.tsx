import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  Boxes,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import { stockBySucursal, stockResumen } from "@/api/stock";
import { listSucursales } from "@/api/sucursales";
import type {
  EstadoReposicion,
  StockSucursalRow,
  Sucursal,
} from "@/lib/types";
import { parseDecimal } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  StockAjusteDialog,
  type StockAjusteTarget,
} from "@/components/stock/stock-ajuste-dialog";
import { useAuth } from "@/store/auth";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

const PER_PAGE = 25;

export const stockRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/stock",
  component: StockPage,
});

type FiltroId =
  | "todos"
  | "bajo_minimo"
  | "en_reorden"
  | "agotado"
  | "sobrestock"
  | "ok";

const FILTROS: { id: FiltroId; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "bajo_minimo", label: "Bajo mínimo" },
  { id: "en_reorden", label: "En reorden" },
  { id: "agotado", label: "Agotado" },
  { id: "sobrestock", label: "Sobrestock" },
  { id: "ok", label: "OK" },
];

const FILTRO_TO_ESTADO: Record<FiltroId, EstadoReposicion | "bajo_minimo" | undefined> = {
  todos: undefined,
  bajo_minimo: "bajo_minimo",
  en_reorden: "reorden",
  agotado: "agotado",
  sobrestock: "sobrestock",
  ok: "ok",
};

function formatMoney(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

function formatThreshold(
  value: number | null | undefined,
  fromDefault: boolean,
): React.ReactNode {
  if (value === null || value === undefined) return <span>—</span>;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1",
        fromDefault && "text-muted-foreground/70",
      )}
      title={fromDefault ? "Heredado del artículo" : "Definido en sucursal"}
    >
      {value}
      {fromDefault && (
        <span className="text-[9px] uppercase tracking-wider rounded-sm bg-muted px-1 py-0.5 text-muted-foreground">
          art
        </span>
      )}
    </span>
  );
}

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  tone?: "default" | "destructive" | "warning" | "rose";
}
function StatCard({ label, value, tone = "default" }: StatCardProps) {
  const toneCls =
    tone === "destructive"
      ? "text-destructive"
      : tone === "warning"
        ? "text-amber-600 dark:text-amber-400"
        : tone === "rose"
          ? "text-rose-600 dark:text-rose-400"
          : "text-foreground";
  return (
    <Card className="p-5">
      <div className="flex flex-col gap-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span
          className={cn(
            "text-[22px] font-semibold tracking-tight tabular-nums leading-none",
            toneCls,
          )}
        >
          {value}
        </span>
      </div>
    </Card>
  );
}

interface RowComputed {
  stockRow: StockSucursalRow;
  cantidad: number;
  pvp: number | null;
  costo: number | null;
  estadoRep: EstadoReposicion;
  efectivoMin: number | null;
  efectivoMax: number | null;
  efectivoReorden: number | null;
  efectivoLeadTime: number | null;
  isMinDefault: boolean;
  isMaxDefault: boolean;
  isReordenDefault: boolean;
}

function StockPage() {
  const user = useAuth((s) => s.user);

  const sucursalesQ = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
    staleTime: 60_000,
  });
  const sucursales: Sucursal[] = sucursalesQ.data ?? [];

  const [sucursalId, setSucursalId] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (sucursalId !== null) return;
    if (sucursales.length === 0) return;
    const userSuc = user?.sucursal_id ?? null;
    const match = userSuc
      ? sucursales.find((s) => s.id === userSuc)
      : undefined;
    setSucursalId((match ?? sucursales[0]).id);
  }, [sucursales, sucursalId, user?.sucursal_id]);

  const [query, setQuery] = React.useState("");
  const [filtro, setFiltro] = React.useState<FiltroId>("todos");
  const [page, setPage] = React.useState(1);
  const debouncedQuery = useDebounced(query, 350);

  const [ajusteTarget, setAjusteTarget] =
    React.useState<StockAjusteTarget | null>(null);
  const [ajusteOpen, setAjusteOpen] = React.useState(false);

  React.useEffect(() => {
    setPage(1);
  }, [debouncedQuery, filtro, sucursalId]);

  const estadoApi = FILTRO_TO_ESTADO[filtro];

  const stockQ = useQuery({
    queryKey: [
      "stock",
      "bySucursal",
      sucursalId,
      page,
      PER_PAGE,
      debouncedQuery,
      estadoApi,
    ],
    queryFn: () =>
      stockBySucursal({
        sucursalId: sucursalId!,
        page,
        perPage: PER_PAGE,
        q: debouncedQuery.trim() || undefined,
        estado: estadoApi as EstadoReposicion | undefined,
      }),
    enabled: Boolean(sucursalId),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  // Conteos por estado (independientes del filtro/búsqueda) para los stat cards.
  const resumenQ = useQuery({
    queryKey: ["stock", "resumen", sucursalId],
    queryFn: () => stockResumen(sucursalId!),
    enabled: Boolean(sucursalId),
    staleTime: 30_000,
  });

  const rows: RowComputed[] = React.useMemo(() => {
    const items = stockQ.data?.items ?? [];
    const out: RowComputed[] = [];
    for (const r of items) {
      const cantidad = parseDecimal(r.cantidad) ?? 0;
      const pvp = parseDecimal(r.articulo?.pvp_base ?? null);
      const costo = parseDecimal(r.articulo?.costo ?? null);
      const efectivoMin = parseDecimal(r.efectivo_minimo ?? null);
      const efectivoMax = parseDecimal(r.efectivo_maximo ?? null);
      const efectivoReorden = parseDecimal(r.efectivo_reorden ?? null);
      const isMinDefault =
        efectivoMin !== null &&
        (r.stock_minimo === null || r.stock_minimo === undefined);
      const isMaxDefault =
        efectivoMax !== null &&
        (r.stock_maximo === null || r.stock_maximo === undefined);
      const isReordenDefault =
        efectivoReorden !== null &&
        (r.punto_reorden === null || r.punto_reorden === undefined);
      const estadoRep: EstadoReposicion = r.estado_reposicion ?? "ok";
      out.push({
        stockRow: r,
        cantidad,
        pvp,
        costo,
        estadoRep,
        efectivoMin,
        efectivoMax,
        efectivoReorden,
        efectivoLeadTime: r.efectivo_lead_time ?? null,
        isMinDefault,
        isMaxDefault,
        isReordenDefault,
      });
    }
    return out;
  }, [stockQ.data?.items]);

  const stats = React.useMemo(() => {
    const r = resumenQ.data;
    if (!r) {
      return { totalArt: 0, bajoMin: 0, enReorden: 0, sobrestock: 0 };
    }
    return {
      totalArt: r.total,
      bajoMin: r.agotado + r.critico,
      enReorden: r.reorden,
      sobrestock: r.sobrestock,
    };
  }, [resumenQ.data]);

  const total = stockQ.data?.total ?? 0;
  const pages = stockQ.data?.pages ?? 1;
  const sliceFrom = (page - 1) * PER_PAGE;
  const sliceTo = Math.min(sliceFrom + PER_PAGE, total);

  const sucursalActual = sucursales.find((s) => s.id === sucursalId);

  const isLoading =
    sucursalesQ.isLoading || stockQ.isLoading || !sucursalId;

  const openAjuste = (r: RowComputed) => {
    if (!sucursalId || !sucursalActual) return;
    const sr = r.stockRow;
    const art = sr.articulo;
    if (!art) return;
    setAjusteTarget({
      // El dialog espera un Articulo completo — armamos uno mínimo con lo embedded.
      articulo: {
        id: art.id,
        codigo: art.codigo,
        descripcion: art.descripcion,
        costo: art.costo ?? null,
        pvp_base: art.pvp_base ?? null,
      } as StockAjusteTarget["articulo"],
      sucursalId,
      sucursalNombre: sucursalActual.nombre,
      cantidadActual: r.cantidad,
      stockMinimo:
        sr.stock_minimo !== null && sr.stock_minimo !== undefined
          ? parseDecimal(sr.stock_minimo)
          : null,
      stockMaximo:
        sr.stock_maximo !== null && sr.stock_maximo !== undefined
          ? parseDecimal(sr.stock_maximo)
          : null,
      puntoReorden:
        sr.punto_reorden !== null && sr.punto_reorden !== undefined
          ? parseDecimal(sr.punto_reorden)
          : null,
      leadTimeDias: sr.lead_time_dias ?? null,
      efectivoMin: r.efectivoMin,
      efectivoMax: r.efectivoMax,
      efectivoReorden: r.efectivoReorden,
      efectivoLeadTime: r.efectivoLeadTime,
    });
    setAjusteOpen(true);
  };

  return (
    <div className="flex flex-col gap-8 max-w-[1280px]">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Stock
          </h2>
          <p className="mt-1.5 text-[14px] text-muted-foreground">
            Hacé clic en una fila para ajustar la cantidad.
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Sucursal
          </span>
          <select
            value={sucursalId ?? ""}
            onChange={(e) => setSucursalId(Number(e.target.value))}
            disabled={sucursalesQ.isLoading}
            className={cn(
              "h-10 min-w-[200px] rounded-lg border border-input bg-background px-3 py-2 text-[14px]",
              "ring-offset-background transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {sucursales.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nombre}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total"
          value={
            resumenQ.isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              stats.totalArt
            )
          }
        />
        <StatCard
          label="Bajo mínimo"
          value={
            resumenQ.isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              stats.bajoMin
            )
          }
          tone={stats.bajoMin > 0 ? "destructive" : "default"}
        />
        <StatCard
          label="En reorden"
          value={
            resumenQ.isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              stats.enReorden
            )
          }
          tone={stats.enReorden > 0 ? "warning" : "default"}
        />
        <StatCard
          label="Sobrestock"
          value={
            resumenQ.isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              stats.sobrestock
            )
          }
          tone={stats.sobrestock > 0 ? "rose" : "default"}
        />
      </div>

      <div className="flex flex-col gap-4">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-[16px] w-[16px] text-muted-foreground"
            strokeWidth={1.5}
          />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por código o descripción…"
            className="h-10 pl-9"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {FILTROS.map((f) => {
            const active = filtro === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setFiltro(f.id)}
                className={cn(
                  "h-8 px-3 rounded-full border text-[12px] font-medium transition-colors duration-200 ease-apple",
                  active
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-transparent text-muted-foreground hover:bg-muted/50",
                )}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      <Card className="overflow-hidden p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[120px]">Código</TableHead>
              <TableHead>Descripción</TableHead>
              <TableHead className="w-[100px] text-right">Cantidad</TableHead>
              <TableHead className="w-[80px] text-right">Mín</TableHead>
              <TableHead className="w-[90px] text-right">Reorden</TableHead>
              <TableHead className="w-[80px] text-right">Máx</TableHead>
              <TableHead className="w-[120px] text-right">Precio</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                    <TableCell colSpan={7}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : rows.map((r) => {
                  const art = r.stockRow.articulo;
                  if (!art) return null;
                  const cantColor =
                    r.estadoRep === "agotado" || r.estadoRep === "critico"
                      ? "text-destructive"
                      : r.estadoRep === "reorden"
                        ? "text-amber-600 dark:text-amber-400"
                        : r.estadoRep === "sobrestock"
                          ? "text-rose-600 dark:text-rose-400"
                          : "text-foreground";
                  return (
                    <TableRow
                      key={r.stockRow.id}
                      className="cursor-pointer"
                      onClick={() => openAjuste(r)}
                    >
                      <TableCell className="font-mono text-[12px] text-muted-foreground">
                        {art.codigo}
                      </TableCell>
                      <TableCell className="font-medium text-foreground">
                        {art.descripcion}
                        {r.estadoRep === "agotado" && (
                          <Badge
                            variant="destructive"
                            className="ml-2 align-middle"
                          >
                            Agotado
                          </Badge>
                        )}
                        {r.estadoRep === "critico" && (
                          <Badge
                            variant="destructive"
                            className="ml-2 align-middle"
                          >
                            Bajo mínimo
                          </Badge>
                        )}
                        {r.estadoRep === "reorden" && (
                          <Badge
                            variant="outline"
                            className="ml-2 align-middle border-amber-500/40 text-amber-600 dark:text-amber-400"
                          >
                            Reorden
                          </Badge>
                        )}
                        {r.estadoRep === "sobrestock" && (
                          <Badge
                            variant="outline"
                            className="ml-2 align-middle border-rose-500/40 text-rose-600 dark:text-rose-400"
                          >
                            Sobrestock
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell
                        className={cn(
                          "text-right tabular-nums font-medium",
                          cantColor,
                        )}
                      >
                        {r.cantidad}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-[13px] text-muted-foreground">
                        {formatThreshold(r.efectivoMin, r.isMinDefault)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-[13px] text-muted-foreground">
                        {formatThreshold(r.efectivoReorden, r.isReordenDefault)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-[13px] text-muted-foreground">
                        {formatThreshold(r.efectivoMax, r.isMaxDefault)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-[13px]">
                        {formatMoney(r.pvp)}
                      </TableCell>
                    </TableRow>
                  );
                })}

            {!isLoading && rows.length === 0 && !stockQ.isError && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={7} className="py-16">
                  <div className="flex flex-col items-center gap-3 text-center">
                    <div className="rounded-full bg-muted/60 p-3">
                      <Boxes
                        className="h-6 w-6 text-muted-foreground"
                        strokeWidth={1.5}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <p className="text-[14px] font-medium text-foreground">
                        {debouncedQuery || filtro !== "todos"
                          ? "Sin resultados"
                          : "Esta sucursal no tiene stock cargado"}
                      </p>
                      <p className="text-[13px] text-muted-foreground">
                        {debouncedQuery
                          ? `No encontramos artículos para “${debouncedQuery}”.`
                          : "Cuando registres el primer movimiento, aparecerá acá."}
                      </p>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {stockQ.isError && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={7} className="py-12 text-center">
                  <p className="text-[13px] text-destructive">
                    No pudimos cargar el stock.
                  </p>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      <div className="flex items-center justify-between gap-4">
        <p className="text-[13px] text-muted-foreground tabular-nums">
          {total === 0
            ? "Sin filas"
            : `Mostrando ${sliceFrom + 1}-${sliceTo} de ${total}`}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || stockQ.isFetching}
          >
            <ChevronLeft strokeWidth={1.5} />
            Anterior
          </Button>
          <span className="text-[13px] tabular-nums text-muted-foreground min-w-[64px] text-center">
            {page} / {Math.max(1, pages)}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page >= pages || stockQ.isFetching}
          >
            Siguiente
            <ChevronRight strokeWidth={1.5} />
          </Button>
        </div>
      </div>

      <StockAjusteDialog
        target={ajusteTarget}
        open={ajusteOpen}
        onOpenChange={(o) => {
          setAjusteOpen(o);
          if (!o) setAjusteTarget(null);
        }}
      />
    </div>
  );
}
