import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ChevronDown,
  Download,
  Network,
  Sparkles,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { formatNumber } from "@/lib/format";
import {
  getCorrelaciones,
  type CorrelacionRegla,
  type CorrelacionesResponse,
} from "@/api/reports";

type Ventana = 30 | 60 | 90;

const VENTANA_LABELS: Record<Ventana, string> = {
  30: "Últimos 30 días",
  60: "Últimos 60 días",
  90: "Últimos 90 días",
};

interface CorrelacionesCardProps {
  sucursalId: number | null;
}

function rangoFromVentana(ventana: Ventana): {
  fecha_desde: string;
  fecha_hasta: string;
} {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const desde = new Date(today);
  desde.setDate(today.getDate() - (ventana - 1));
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`;
  return { fecha_desde: fmt(desde), fecha_hasta: fmt(today) };
}

function liftTier(lift: number): "alto" | "medio" | "bajo" {
  if (lift >= 2.5) return "alto";
  if (lift >= 1.5) return "medio";
  return "bajo";
}

function formatLift(lift: number): string {
  if (!Number.isFinite(lift)) return "—";
  if (lift >= 100) return lift.toFixed(0);
  return lift.toFixed(2);
}

function formatPct(v: number): string {
  if (!Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function ItemBadges({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      {items.map((it, i) => (
        <Badge
          key={`${it}-${i}`}
          variant="secondary"
          className="px-2 py-0.5 text-[11px] max-w-[220px] truncate"
          title={it}
        >
          {it}
        </Badge>
      ))}
    </div>
  );
}

function LiftDot({ lift }: { lift: number }) {
  const tier = liftTier(lift);
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full shrink-0",
        tier === "alto" &&
          "bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.18)] animate-pulse-soft",
        tier === "medio" && "bg-amber-500",
        tier === "bajo" && "bg-muted-foreground/50",
      )}
      aria-hidden
    />
  );
}

export function CorrelacionesCard({ sucursalId }: CorrelacionesCardProps) {
  const [ventana, setVentana] = React.useState<Ventana>(60);
  const [detalleOpen, setDetalleOpen] = React.useState(false);

  const rango = React.useMemo(() => rangoFromVentana(ventana), [ventana]);

  const params = React.useMemo(
    () => ({
      ...rango,
      ...(sucursalId ? { sucursal_id: sucursalId } : {}),
      // Defaults adaptados al backend; permitimos al usuario refinar en el modal.
      top_n: 50,
    }),
    [rango, sucursalId],
  );

  const correlacionesQ = useQuery({
    queryKey: ["report-correlaciones", params],
    queryFn: () => getCorrelaciones(params),
    staleTime: 5 * 60 * 1000,
  });

  const data = correlacionesQ.data;
  const reglas = data?.reglas ?? [];

  return (
    <>
      <Card className="p-6 flex flex-col">
        <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <div className="rounded-[10px] bg-primary/10 p-2 shrink-0">
              <Network
                className="h-[18px] w-[18px] text-primary"
                strokeWidth={1.5}
              />
            </div>
            <div className="min-w-0">
              <h3 className="text-[15px] font-semibold tracking-tight leading-tight flex items-center gap-2">
                Productos que se compran juntos
                <Sparkles
                  className="h-3.5 w-3.5 text-primary/70"
                  strokeWidth={1.5}
                />
              </h3>
              <p className="text-[12px] text-muted-foreground mt-0.5">
                {data
                  ? `Market basket sobre ${formatNumber(
                      data.transacciones_analizadas,
                    )} transacciones · ${formatNumber(
                      data.items_unicos,
                    )} items únicos`
                  : "Análisis de market basket sobre el período"}
              </p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2">
                <span className="font-medium">{VENTANA_LABELS[ventana]}</span>
                <ChevronDown
                  className="h-3.5 w-3.5 opacity-60"
                  strokeWidth={1.5}
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[180px]">
              <DropdownMenuLabel>Ventana</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {([30, 60, 90] as Ventana[]).map((v) => (
                <DropdownMenuItem
                  key={v}
                  onSelect={() => setVentana(v)}
                  className={
                    ventana === v
                      ? "bg-muted/60 font-medium text-foreground"
                      : ""
                  }
                >
                  {VENTANA_LABELS[v]}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {correlacionesQ.isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-[52px] w-full rounded-[10px]" />
            ))}
          </div>
        ) : correlacionesQ.isError ? (
          <EmptyState
            title="No se pudo calcular el análisis"
            message="Reintentá en unos segundos o ajustá la ventana de tiempo."
          />
        ) : reglas.length === 0 ? (
          <EmptyState
            title="Sin patrones detectados"
            message="No se encontraron asociaciones significativas en este período. Probá ampliar la ventana o reducir thresholds en el detalle."
          />
        ) : (
          <>
            <ul className="flex flex-col divide-y divide-border/60">
              {reglas.slice(0, 10).map((r, i) => (
                <ReglaRow key={`${i}-${r.lift}`} regla={r} />
              ))}
            </ul>
            <div className="mt-4 flex items-center justify-between gap-2">
              <p className="text-[11px] text-muted-foreground">
                Mostrando top 10 de {reglas.length} reglas (orden por lift).
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDetalleOpen(true)}
                className="gap-1"
              >
                Ver análisis completo
                <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} />
              </Button>
            </div>
          </>
        )}
      </Card>

      <CorrelacionesDetalleModal
        open={detalleOpen}
        onOpenChange={setDetalleOpen}
        data={data}
      />
    </>
  );
}

interface ReglaRowProps {
  regla: CorrelacionRegla;
}

function ReglaRow({ regla }: ReglaRowProps) {
  const tier = liftTier(regla.lift);
  return (
    <li className="py-3 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-2 md:gap-4 md:items-center">
      <div className="flex flex-wrap items-center gap-2 min-w-0">
        <ItemBadges items={regla.antecedentes_desc} />
        <ArrowRight
          className="h-3.5 w-3.5 text-muted-foreground shrink-0"
          strokeWidth={1.5}
        />
        <ItemBadges items={regla.consecuentes_desc} />
      </div>
      <div className="flex items-center gap-3 text-[11px] tabular-nums shrink-0">
        <div className="flex items-center gap-1.5">
          <LiftDot lift={regla.lift} />
          <span
            className={cn(
              "font-semibold",
              tier === "alto" && "text-emerald-700 dark:text-emerald-400",
              tier === "medio" && "text-amber-700 dark:text-amber-400",
              tier === "bajo" && "text-muted-foreground",
            )}
          >
            lift {formatLift(regla.lift)}
          </span>
        </div>
        <span className="text-muted-foreground">
          conf {formatPct(regla.confianza)}
        </span>
        <span className="text-muted-foreground hidden sm:inline">
          sop {formatPct(regla.soporte)}
        </span>
      </div>
    </li>
  );
}

function EmptyState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center text-muted-foreground">
      <div className="rounded-full bg-muted/60 p-3 mb-3">
        <Network className="h-5 w-5 opacity-50" strokeWidth={1.5} />
      </div>
      <p className="text-[14px] font-medium text-foreground">{title}</p>
      <p className="text-[12px] mt-1 max-w-[420px]">{message}</p>
    </div>
  );
}

// --- Modal con tabla completa ------------------------------------------------

interface DetalleModalProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  data: CorrelacionesResponse | undefined;
}

type SortKey = "lift" | "confianza" | "soporte";

function CorrelacionesDetalleModal({
  open,
  onOpenChange,
  data,
}: DetalleModalProps) {
  const [liftMin, setLiftMin] = React.useState(0);
  const [confMin, setConfMin] = React.useState(0);
  const [sortKey, setSortKey] = React.useState<SortKey>("lift");
  const [sortDesc, setSortDesc] = React.useState(true);

  React.useEffect(() => {
    if (open) {
      setLiftMin(0);
      setConfMin(0);
      setSortKey("lift");
      setSortDesc(true);
    }
  }, [open]);

  const reglas = React.useMemo<CorrelacionRegla[]>(() => {
    if (!data) return [];
    const filtered = data.reglas.filter(
      (r) => r.lift >= liftMin && r.confianza >= confMin,
    );
    const sorted = [...filtered].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      return sortDesc ? vb - va : va - vb;
    });
    return sorted;
  }, [data, liftMin, confMin, sortKey, sortDesc]);

  const handleExportCSV = () => {
    if (!data) return;
    const header = [
      "antecedentes_codigos",
      "antecedentes_desc",
      "consecuentes_codigos",
      "consecuentes_desc",
      "soporte",
      "confianza",
      "lift",
    ];
    const rows = reglas.map((r) => [
      r.antecedentes_codigos.join("|"),
      r.antecedentes_desc.join("|"),
      r.consecuentes_codigos.join("|"),
      r.consecuentes_desc.join("|"),
      r.soporte.toString(),
      r.confianza.toString(),
      r.lift.toString(),
    ]);
    const escape = (v: string) => {
      const s = String(v ?? "");
      if (/[",\n;]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
      return s;
    };
    const csv = [header, ...rows]
      .map((row) => row.map(escape).join(";"))
      .join("\r\n");
    const blob = new Blob([`﻿${csv}`], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `correlaciones-${data.fecha_desde}_${data.fecha_hasta}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const onSort = (key: SortKey) => {
    if (key === sortKey) setSortDesc((s) => !s);
    else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl w-full max-h-[88vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Network
              className="h-[18px] w-[18px] text-primary"
              strokeWidth={1.5}
            />
            Análisis completo de correlaciones
          </DialogTitle>
          {data && (
            <p className="text-[12px] text-muted-foreground">
              {data.fecha_desde} → {data.fecha_hasta} ·{" "}
              {formatNumber(data.transacciones_analizadas)} transacciones ·{" "}
              {formatNumber(data.items_unicos)} items únicos
            </p>
          )}
        </DialogHeader>

        <div className="flex flex-wrap items-end gap-4 py-3 border-y border-border/60">
          <div className="flex flex-col gap-1.5 min-w-[180px]">
            <label className="text-[11px] font-medium text-muted-foreground">
              Lift mínimo:{" "}
              <span className="text-foreground tabular-nums">
                {liftMin.toFixed(2)}
              </span>
            </label>
            <input
              type="range"
              min={0}
              max={10}
              step={0.1}
              value={liftMin}
              onChange={(e) => setLiftMin(parseFloat(e.target.value))}
              className="accent-primary"
            />
          </div>
          <div className="flex flex-col gap-1.5 min-w-[180px]">
            <label className="text-[11px] font-medium text-muted-foreground">
              Confianza mínima:{" "}
              <span className="text-foreground tabular-nums">
                {(confMin * 100).toFixed(0)}%
              </span>
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={confMin}
              onChange={(e) => setConfMin(parseFloat(e.target.value))}
              className="accent-primary"
            />
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {reglas.length} reglas
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportCSV}
              className="gap-2"
              disabled={!data || reglas.length === 0}
            >
              <Download className="h-3.5 w-3.5" strokeWidth={1.5} />
              Exportar CSV
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-auto -mx-6 px-6">
          {!data ? (
            <div className="py-10 text-center text-muted-foreground text-[13px]">
              Cargando...
            </div>
          ) : reglas.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground text-[13px]">
              Sin reglas que cumplan los filtros.
            </div>
          ) : (
            <table className="w-full text-[12px]">
              <thead className="sticky top-0 bg-card z-10">
                <tr className="border-b border-border/60 text-left text-muted-foreground">
                  <th className="py-2 pr-4 font-medium">Antecedentes</th>
                  <th className="py-2 pr-4 font-medium">Consecuentes</th>
                  <SortableTh
                    label="Soporte"
                    active={sortKey === "soporte"}
                    desc={sortDesc}
                    onClick={() => onSort("soporte")}
                  />
                  <SortableTh
                    label="Confianza"
                    active={sortKey === "confianza"}
                    desc={sortDesc}
                    onClick={() => onSort("confianza")}
                  />
                  <SortableTh
                    label="Lift"
                    active={sortKey === "lift"}
                    desc={sortDesc}
                    onClick={() => onSort("lift")}
                  />
                </tr>
              </thead>
              <tbody>
                {reglas.map((r, i) => (
                  <tr
                    key={i}
                    className="border-b border-border/40 hover:bg-muted/30 transition-colors"
                  >
                    <td className="py-2 pr-4 align-top">
                      <ItemBadges items={r.antecedentes_desc} />
                    </td>
                    <td className="py-2 pr-4 align-top">
                      <ItemBadges items={r.consecuentes_desc} />
                    </td>
                    <td className="py-2 pr-4 align-top tabular-nums text-muted-foreground">
                      {formatPct(r.soporte)}
                    </td>
                    <td className="py-2 pr-4 align-top tabular-nums text-muted-foreground">
                      {formatPct(r.confianza)}
                    </td>
                    <td className="py-2 pr-4 align-top tabular-nums">
                      <span className="inline-flex items-center gap-1.5">
                        <LiftDot lift={r.lift} />
                        <span className="font-semibold">
                          {formatLift(r.lift)}
                        </span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SortableTh({
  label,
  active,
  desc,
  onClick,
}: {
  label: string;
  active: boolean;
  desc: boolean;
  onClick: () => void;
}) {
  return (
    <th className="py-2 pr-4 font-medium">
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1 transition-colors",
          active ? "text-foreground" : "hover:text-foreground",
        )}
      >
        {label}
        <ChevronDown
          className={cn(
            "h-3 w-3 transition-transform",
            active ? "opacity-100" : "opacity-30",
            active && !desc && "rotate-180",
          )}
          strokeWidth={1.5}
        />
      </button>
    </th>
  );
}
