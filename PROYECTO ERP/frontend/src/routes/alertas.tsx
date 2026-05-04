import * as React from "react";
import { createRoute, redirect } from "@tanstack/react-router";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  Eye,
  Play,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import { useAuth } from "@/store/auth";
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
import {
  listAlertas,
  patchAlerta,
  runAlertasDetection,
  type AlertasQuery,
} from "@/api/alertas";
import type { Alerta, EstadoAlerta, Severidad, TipoAlerta } from "@/lib/types";
import { AlertaDetalleDialog } from "@/components/alertas/alerta-detalle-dialog";
import {
  estadoAlertaLabel,
  estadoBadgeVariant,
  relativeTime,
  severidadBadgeVariant,
  severidadLabel,
  tipoAlertaLabel,
} from "@/components/alertas/format";
import { cn } from "@/lib/utils";
import { appLayoutRoute } from "./app-layout";

const PER_PAGE = 20;

export const alertasRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/alertas",
  beforeLoad: () => {
    const { user } = useAuth.getState();
    if (user?.rol !== "admin") {
      throw redirect({ to: "/" });
    }
  },
  component: AlertasPage,
});

type Chip =
  | "todas"
  | "nueva"
  | "en_revision"
  | "criticas"
  | "confirmadas"
  | "descartadas";

const CHIPS: { id: Chip; label: string }[] = [
  { id: "todas", label: "Todas abiertas" },
  { id: "nueva", label: "Nuevas" },
  { id: "en_revision", label: "En revisión" },
  { id: "criticas", label: "Críticas" },
  { id: "confirmadas", label: "Confirmadas" },
  { id: "descartadas", label: "Descartadas" },
];

function AlertasPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [chip, setChip] = React.useState<Chip>("todas");
  const [tipoFilter, setTipoFilter] = React.useState<TipoAlerta | "">("");
  const [page, setPage] = React.useState(1);
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [detailOpen, setDetailOpen] = React.useState(false);

  React.useEffect(() => {
    setPage(1);
  }, [chip, tipoFilter]);

  const queryParams: AlertasQuery = React.useMemo(() => {
    const params: AlertasQuery = { page, per_page: PER_PAGE };
    if (chip === "nueva") params.estado = "nueva";
    else if (chip === "en_revision") params.estado = "en_revision";
    else if (chip === "confirmadas") params.estado = "confirmada";
    else if (chip === "descartadas") {
      params.estado = "descartada";
      params.incluir_cerradas = true;
    } else if (chip === "criticas") {
      params.severidad = "critica" as Severidad;
    }
    if (tipoFilter) params.tipo = tipoFilter;
    return params;
  }, [chip, tipoFilter, page]);

  const listQ = useQuery({
    queryKey: ["alertas", queryParams],
    queryFn: () => listAlertas(queryParams),
    placeholderData: keepPreviousData,
  });

  const resumenQ = useQuery({
    queryKey: ["alertas-resumen"],
    queryFn: async () => {
      const { getAlertasResumen } = await import("@/api/alertas");
      return getAlertasResumen();
    },
    refetchInterval: 60_000,
  });

  const runMut = useMutation({
    mutationFn: () => runAlertasDetection(90),
    onSuccess: (data) => {
      if (data.creadas === 0) {
        toast({
          title: "Sin alertas nuevas",
          description: `Corrieron ${data.detectores} detectores sin novedad.`,
        });
      } else {
        toast({
          title: `${data.creadas} alerta${data.creadas > 1 ? "s" : ""} nueva${data.creadas > 1 ? "s" : ""}`,
          description: "Revisalas en la lista de abajo.",
        });
      }
      qc.invalidateQueries({ queryKey: ["alertas"] });
      qc.invalidateQueries({ queryKey: ["alertas-resumen"] });
    },
    onError: () => {
      toast({
        title: "Error al correr detección",
        description: "Volvé a intentar en unos segundos.",
        variant: "destructive",
      });
    },
  });

  const patchMut = useMutation({
    mutationFn: ({ id, estado }: { id: number; estado: EstadoAlerta }) =>
      patchAlerta(id, { estado }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alertas"] });
      qc.invalidateQueries({ queryKey: ["alertas-resumen"] });
    },
  });

  const items = listQ.data?.items ?? [];
  const total = listQ.data?.total ?? 0;
  const pages = listQ.data?.pages ?? 1;

  const openDetail = (id: number) => {
    setSelectedId(id);
    setDetailOpen(true);
  };

  return (
    <div className="flex flex-col gap-7 max-w-[1280px]">
      {/* Header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
            Alertas de inconsistencias
          </h2>
          <p className="mt-1 text-[14px] text-muted-foreground max-w-[640px]">
            Detección automática de patrones sospechosos: pagos duplicados,
            facturas repetidas, anulaciones frecuentes, ajustes de stock sin
            justificar y más.
          </p>
        </div>
        <Button onClick={() => runMut.mutate()} disabled={runMut.isPending}>
          {runMut.isPending ? (
            <Sparkles className="animate-pulse" strokeWidth={1.5} />
          ) : (
            <Play strokeWidth={1.5} />
          )}
          Correr detección
        </Button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Nuevas"
          value={resumenQ.data?.nuevas ?? null}
          icon={AlertTriangle}
          tone="default"
        />
        <StatCard
          label="En revisión"
          value={resumenQ.data?.en_revision ?? null}
          icon={Clock}
          tone="muted"
        />
        <StatCard
          label="Críticas"
          value={resumenQ.data?.criticas ?? null}
          icon={ShieldAlert}
          tone="destructive"
        />
        <StatCard
          label="Últimas 24h"
          value={resumenQ.data?.ultimas_24h ?? null}
          icon={Sparkles}
          tone="muted"
        />
      </div>

      {/* Chips + filter por tipo */}
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

        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Tipo
          </span>
          <select
            value={tipoFilter}
            onChange={(e) => setTipoFilter(e.target.value as TipoAlerta | "")}
            className="h-8 rounded-[8px] border border-border bg-background px-2 text-[12px] focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Todos</option>
            <option value="pago_duplicado">Pago duplicado</option>
            <option value="factura_compra_repetida">
              Factura compra repetida
            </option>
            <option value="items_repetidos_diff_nro">Items repetidos</option>
            <option value="anulaciones_frecuentes">
              Anulaciones frecuentes
            </option>
            <option value="ajuste_stock_sospechoso">
              Ajuste stock sospechoso
            </option>
          </select>
        </div>
      </div>

      {/* Tabla */}
      <Card className="overflow-hidden p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[120px]">Detectada</TableHead>
              <TableHead className="w-[120px]">Severidad</TableHead>
              <TableHead className="w-[180px]">Tipo</TableHead>
              <TableHead>Descripción</TableHead>
              <TableHead className="w-[120px]">Estado</TableHead>
              <TableHead className="w-[140px] text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {listQ.isLoading && items.length === 0
              ? Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                    <TableCell colSpan={6}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : items.map((a) => (
                  <AlertaRow
                    key={a.id}
                    alerta={a}
                    onView={() => openDetail(a.id)}
                    onConfirm={() =>
                      patchMut.mutate({ id: a.id, estado: "confirmada" })
                    }
                    onDiscard={() =>
                      patchMut.mutate({ id: a.id, estado: "descartada" })
                    }
                  />
                ))}

            {!listQ.isLoading && items.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={6} className="py-16">
                  <div className="flex flex-col items-center gap-3 text-center">
                    <div className="rounded-full bg-muted/60 p-3">
                      <ShieldAlert
                        className="h-6 w-6 text-muted-foreground"
                        strokeWidth={1.5}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <p className="text-[14px] font-medium text-foreground">
                        Sin alertas en este filtro
                      </p>
                      <p className="text-[13px] text-muted-foreground">
                        Probá correr la detección o cambiar de filtro.
                      </p>
                    </div>
                  </div>
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
            ? "Sin alertas"
            : `Mostrando ${(page - 1) * PER_PAGE + 1}-${Math.min(page * PER_PAGE, total)} de ${total}`}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || listQ.isLoading}
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
            disabled={page >= (pages || 1) || listQ.isLoading}
          >
            Siguiente
            <ChevronRight strokeWidth={1.5} />
          </Button>
        </div>
      </div>

      <AlertaDetalleDialog
        alertaId={selectedId}
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

function StatCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number | null;
  icon: typeof AlertTriangle;
  tone: "default" | "destructive" | "muted";
}) {
  const toneClasses =
    tone === "destructive"
      ? "text-destructive"
      : tone === "muted"
        ? "text-muted-foreground"
        : "text-foreground";
  return (
    <Card className="p-4 flex items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span
          className={cn(
            "text-[26px] font-semibold tracking-tight tabular-nums",
            toneClasses,
          )}
        >
          {value === null ? "—" : value}
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

function AlertaRow({
  alerta,
  onView,
  onConfirm,
  onDiscard,
}: {
  alerta: Alerta;
  onView: () => void;
  onConfirm: () => void;
  onDiscard: () => void;
}) {
  return (
    <TableRow className="cursor-pointer" onClick={onView}>
      <TableCell className="text-[13px] text-muted-foreground tabular-nums whitespace-nowrap">
        {relativeTime(alerta.detected_at)}
      </TableCell>
      <TableCell>
        <Badge variant={severidadBadgeVariant(alerta.severidad)}>
          {severidadLabel(alerta.severidad)}
        </Badge>
      </TableCell>
      <TableCell>
        <Badge variant="outline">{tipoAlertaLabel(alerta.tipo)}</Badge>
      </TableCell>
      <TableCell className="max-w-[480px]">
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-[13px] font-medium truncate">
            {alerta.titulo}
          </span>
          <span className="text-[12px] text-muted-foreground line-clamp-1">
            {alerta.descripcion}
          </span>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={estadoBadgeVariant(alerta.estado)}>
          {estadoAlertaLabel(alerta.estado)}
        </Badge>
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={(e) => {
              e.stopPropagation();
              onView();
            }}
            title="Ver detalle"
          >
            <Eye className="h-4 w-4" strokeWidth={1.5} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            disabled={alerta.estado === "confirmada"}
            onClick={(e) => {
              e.stopPropagation();
              onConfirm();
            }}
            title="Confirmar"
          >
            <Check className="h-4 w-4" strokeWidth={1.5} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            disabled={alerta.estado === "descartada"}
            onClick={(e) => {
              e.stopPropagation();
              onDiscard();
            }}
            title="Descartar"
          >
            <X className="h-4 w-4" strokeWidth={1.5} />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}
