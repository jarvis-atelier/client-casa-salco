import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  FileDown,
  Loader2,
  PackagePlus,
  RefreshCw,
} from "lucide-react";
import {
  crearOrdenCompra,
  downloadListaReposicionXlsx,
  getReposicion,
  recalcularReposicion,
} from "@/api/reposicion";
import { listSucursales } from "@/api/sucursales";
import type {
  ReposicionGrupo,
  ReposicionItem,
  Sucursal,
  UrgenciaReposicion,
} from "@/lib/types";
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
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/store/auth";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

export const stockReposicionRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/stock/reposicion",
  component: StockReposicionPage,
});

function formatMoney(n: string | number | null | undefined): string {
  if (n === null || n === undefined || n === "") return "—";
  const v = typeof n === "string" ? Number.parseFloat(n) : n;
  if (!Number.isFinite(v)) return "—";
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(v);
}

function formatNumber(n: string | number | null | undefined): string {
  if (n === null || n === undefined || n === "") return "—";
  const v = typeof n === "string" ? Number.parseFloat(n) : n;
  if (!Number.isFinite(v)) return "—";
  return new Intl.NumberFormat("es-AR").format(v);
}

const URGENCIA_LABEL: Record<UrgenciaReposicion, string> = {
  critica: "Crítica",
  alta: "Alta",
  media: "Media",
};

function urgenciaBadgeClass(u: UrgenciaReposicion): string {
  if (u === "critica") {
    return "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-400";
  }
  if (u === "alta") {
    return "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400";
  }
  return "border-border bg-muted/50 text-muted-foreground";
}

function StockReposicionPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);

  const sucursalesQ = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
    staleTime: 60_000,
  });
  const sucursales: Sucursal[] = sucursalesQ.data ?? [];

  const [sucursalId, setSucursalId] = React.useState<number | "all">("all");

  React.useEffect(() => {
    if (sucursalId !== "all") return;
    const userSuc = user?.sucursal_id ?? null;
    if (userSuc && sucursales.some((s) => s.id === userSuc)) {
      setSucursalId(userSuc);
    }
  }, [sucursales, sucursalId, user?.sucursal_id]);

  const reposQ = useQuery({
    queryKey: ["reposicion", sucursalId],
    queryFn: () =>
      getReposicion(sucursalId === "all" ? undefined : sucursalId),
    staleTime: 30_000,
  });

  const recalcMut = useMutation({
    mutationFn: () =>
      recalcularReposicion(sucursalId === "all" ? undefined : sucursalId),
    onSuccess: (res) => {
      toast({
        title: "Recálculo completado",
        description: `${res.filas_recalculadas} filas recalculadas · ${res.reorden_seteado} con reorden auto`,
      });
      qc.invalidateQueries({ queryKey: ["reposicion"] });
      qc.invalidateQueries({ queryKey: ["stock"] });
    },
    onError: () => {
      toast({
        title: "No pudimos recalcular",
        description: "Probá de nuevo en un momento.",
        variant: "destructive",
      });
    },
  });

  const orderMut = useMutation({
    mutationFn: (grupo: ReposicionGrupo) => {
      // Una OC por sucursal del grupo (suelen tener todos la misma si filtraste)
      // Si vienen items de varias sucursales, agrupamos por sucursal.
      const bySucursal = new Map<number, ReposicionItem[]>();
      for (const it of grupo.items) {
        const sid = it.sucursal.id;
        if (!bySucursal.has(sid)) bySucursal.set(sid, []);
        bySucursal.get(sid)!.push(it);
      }
      // Creamos UNA OC por (sucursal, proveedor). Devolvemos la primera (de ahora).
      const targetSucId = bySucursal.keys().next().value as number;
      const items = bySucursal.get(targetSucId)!;
      return crearOrdenCompra({
        proveedor_id: grupo.proveedor?.id ?? null,
        sucursal_id: targetSucId,
        items: items.map((it) => ({
          articulo_id: it.articulo.id,
          cantidad: it.cantidad_a_pedir,
          costo_unitario: it.costo_unitario,
        })),
      });
    },
    onSuccess: (res, grupo) => {
      const prov = grupo.proveedor?.razon_social ?? "Sin proveedor";
      toast({
        title: "Orden borrador creada",
        description: `${prov} · ${res.tipo} #${res.numero} · ${formatMoney(res.total)}`,
      });
      qc.invalidateQueries({ queryKey: ["reposicion"] });
      qc.invalidateQueries({ queryKey: ["facturas"] });
    },
    onError: () => {
      toast({
        title: "No pudimos crear la orden",
        description: "Probá de nuevo en un momento.",
        variant: "destructive",
      });
    },
  });

  const isLoading = reposQ.isLoading || sucursalesQ.isLoading;
  const data = reposQ.data;

  const xlsxUrl = downloadListaReposicionXlsx(
    sucursalId === "all" ? undefined : sucursalId,
  );

  return (
    <div className="flex flex-col gap-8 max-w-[1280px]">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Reposición sugerida
          </h2>
          <p className="mt-1.5 text-[14px] text-muted-foreground">
            Artículos en reorden agrupados por proveedor. Generá borradores de
            orden de compra con un click.
          </p>
        </div>

        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Sucursal
            </span>
            <select
              value={sucursalId === "all" ? "all" : String(sucursalId)}
              onChange={(e) => {
                const v = e.target.value;
                setSucursalId(v === "all" ? "all" : Number(v));
              }}
              className={cn(
                "h-10 min-w-[200px] rounded-lg border border-input bg-background px-3 py-2 text-[14px]",
                "ring-offset-background transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              )}
            >
              <option value="all">Todas las sucursales</option>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nombre}
                </option>
              ))}
            </select>
          </div>
          <Button
            variant="outline"
            onClick={() => recalcMut.mutate()}
            disabled={recalcMut.isPending}
          >
            {recalcMut.isPending ? (
              <Loader2 className="animate-spin" strokeWidth={1.5} />
            ) : (
              <RefreshCw strokeWidth={1.5} />
            )}
            Recalcular
          </Button>
          <a href={xlsxUrl}>
            <Button variant="outline">
              <FileDown strokeWidth={1.5} />
              Excel
            </Button>
          </a>
        </div>
      </div>

      {/* Totales */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Sucursales involucradas
          </span>
          <span className="mt-1.5 block text-[22px] font-semibold tracking-tight tabular-nums leading-none">
            {isLoading ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              data?.totales.sucursales ?? 0
            )}
          </span>
        </Card>
        <Card className="p-5">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Artículos a reponer
          </span>
          <span
            className={cn(
              "mt-1.5 block text-[22px] font-semibold tracking-tight tabular-nums leading-none",
              (data?.totales.articulos_a_reponer ?? 0) > 0
                ? "text-rose-600 dark:text-rose-400"
                : "text-foreground",
            )}
          >
            {isLoading ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              data?.totales.articulos_a_reponer ?? 0
            )}
          </span>
        </Card>
        <Card className="p-5">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Valor estimado
          </span>
          <span className="mt-1.5 block text-[22px] font-semibold tracking-tight tabular-nums leading-none">
            {isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              formatMoney(data?.totales.valor_estimado)
            )}
          </span>
        </Card>
      </div>

      {/* Grupos por proveedor */}
      <div className="flex flex-col gap-4">
        {isLoading &&
          Array.from({ length: 2 }).map((_, i) => (
            <Card key={`sk-${i}`} className="p-5">
              <Skeleton className="h-7 w-1/2" />
              <Skeleton className="mt-3 h-5 w-1/3" />
            </Card>
          ))}

        {!isLoading && data && data.por_proveedor.length === 0 && (
          <Card className="p-12">
            <div className="flex flex-col items-center gap-3 text-center">
              <div className="rounded-full bg-emerald-500/10 p-3">
                <PackagePlus
                  className="h-6 w-6 text-emerald-600 dark:text-emerald-400"
                  strokeWidth={1.5}
                />
              </div>
              <p className="text-[15px] font-medium text-foreground">
                Todo en orden
              </p>
              <p className="text-[13px] text-muted-foreground">
                No hay artículos por debajo del punto de reorden.
              </p>
            </div>
          </Card>
        )}

        {!isLoading &&
          data &&
          data.por_proveedor.map((grupo, idx) => (
            <ProveedorGrupoCard
              key={`${grupo.proveedor?.id ?? "noprov"}-${idx}`}
              grupo={grupo}
              onGenerarOC={() => orderMut.mutate(grupo)}
              loading={orderMut.isPending}
            />
          ))}
      </div>
    </div>
  );
}

interface GrupoProps {
  grupo: ReposicionGrupo;
  onGenerarOC: () => void;
  loading: boolean;
}

function ProveedorGrupoCard({ grupo, onGenerarOC, loading }: GrupoProps) {
  const [open, setOpen] = React.useState(true);
  const prov = grupo.proveedor;
  const iniciales =
    (prov?.razon_social ?? "S/P")
      .split(/\s+/)
      .slice(0, 2)
      .map((s) => s[0]?.toUpperCase())
      .join("") || "S";

  return (
    <Card className="overflow-hidden p-0 shadow-apple">
      <div className="flex items-start justify-between gap-4 p-5">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-start gap-4 flex-1 text-left"
        >
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary text-[14px] font-semibold tabular-nums">
            {iniciales}
          </div>
          <div className="flex flex-col gap-1 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[16px] font-semibold tracking-tight text-foreground">
                {prov?.razon_social ?? "Sin proveedor"}
              </span>
              {prov?.cuit && (
                <span className="text-[12px] text-muted-foreground tabular-nums">
                  CUIT {prov.cuit}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[13px] text-muted-foreground">
              <span className="tabular-nums">
                {grupo.total_items} ítem{grupo.total_items === 1 ? "" : "s"}
              </span>
              <span>·</span>
              <span className="tabular-nums">
                {formatMoney(grupo.total_estimado)}
              </span>
              {prov?.email && (
                <>
                  <span>·</span>
                  <span className="truncate">{prov.email}</span>
                </>
              )}
            </div>
          </div>
          {open ? (
            <ChevronDown
              className="h-[18px] w-[18px] text-muted-foreground"
              strokeWidth={1.5}
            />
          ) : (
            <ChevronRight
              className="h-[18px] w-[18px] text-muted-foreground"
              strokeWidth={1.5}
            />
          )}
        </button>
        <Button
          onClick={(e) => {
            e.stopPropagation();
            onGenerarOC();
          }}
          disabled={loading}
        >
          {loading ? (
            <Loader2 className="animate-spin" strokeWidth={1.5} />
          ) : (
            <PackagePlus strokeWidth={1.5} />
          )}
          Generar orden
        </Button>
      </div>

      {open && (
        <div className="border-t border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[120px]">Código</TableHead>
                <TableHead>Descripción</TableHead>
                <TableHead className="w-[160px]">Sucursal</TableHead>
                <TableHead className="w-[100px] text-right">Stock</TableHead>
                <TableHead className="w-[100px] text-right">A pedir</TableHead>
                <TableHead className="w-[120px] text-right">Costo u.</TableHead>
                <TableHead className="w-[130px] text-right">Total</TableHead>
                <TableHead className="w-[100px]">Urgencia</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {grupo.items.map((it) => (
                <TableRow
                  key={`${it.articulo.id}-${it.sucursal.id}`}
                  className="hover:bg-muted/30"
                >
                  <TableCell className="font-mono text-[12px] text-muted-foreground">
                    {it.articulo.codigo}
                  </TableCell>
                  <TableCell className="font-medium text-foreground">
                    {it.articulo.descripcion}
                    {it.articulo.controla_vencimiento && (
                      <Badge
                        variant="outline"
                        className="ml-2 align-middle border-amber-500/40 text-amber-600 dark:text-amber-400"
                      >
                        Perecedero
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-[13px] text-muted-foreground">
                    {it.sucursal.nombre}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[13px]">
                    {formatNumber(it.cantidad_actual)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums font-medium text-foreground">
                    {formatNumber(it.cantidad_a_pedir)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[13px] text-muted-foreground">
                    {formatMoney(it.costo_unitario)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[13px]">
                    {formatMoney(it.total_linea)}
                  </TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
                        urgenciaBadgeClass(it.urgencia),
                      )}
                    >
                      {URGENCIA_LABEL[it.urgencia]}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </Card>
  );
}
