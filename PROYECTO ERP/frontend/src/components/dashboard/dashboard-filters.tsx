import * as React from "react";
import { Calendar, ChevronDown, Filter, Store as StoreIcon } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import type { Sucursal } from "@/lib/types";

export type PeriodPreset =
  | "hoy"
  | "ayer"
  | "esta_semana"
  | "ultimos_7_dias"
  | "ultimos_30_dias"
  | "mes_actual";

export interface DashboardRange {
  preset: PeriodPreset;
  fecha_desde: string; // ISO date YYYY-MM-DD
  fecha_hasta: string;
}

const PRESET_LABELS: Record<PeriodPreset, string> = {
  hoy: "Hoy",
  ayer: "Ayer",
  esta_semana: "Esta semana",
  ultimos_7_dias: "Últimos 7 días",
  ultimos_30_dias: "Últimos 30 días",
  mes_actual: "Mes actual",
};

function fmtDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function resolvePreset(preset: PeriodPreset): DashboardRange {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const startOfWeek = new Date(today);
  // Monday-based week. JS getDay: 0=Sunday..6=Saturday
  const dayIdx = (today.getDay() + 6) % 7; // 0=Mon..6=Sun
  startOfWeek.setDate(today.getDate() - dayIdx);

  const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);

  switch (preset) {
    case "hoy":
      return {
        preset,
        fecha_desde: fmtDate(today),
        fecha_hasta: fmtDate(today),
      };
    case "ayer": {
      const y = new Date(today);
      y.setDate(today.getDate() - 1);
      return { preset, fecha_desde: fmtDate(y), fecha_hasta: fmtDate(y) };
    }
    case "esta_semana":
      return {
        preset,
        fecha_desde: fmtDate(startOfWeek),
        fecha_hasta: fmtDate(today),
      };
    case "ultimos_7_dias": {
      const d = new Date(today);
      d.setDate(today.getDate() - 6);
      return { preset, fecha_desde: fmtDate(d), fecha_hasta: fmtDate(today) };
    }
    case "ultimos_30_dias": {
      const d = new Date(today);
      d.setDate(today.getDate() - 29);
      return { preset, fecha_desde: fmtDate(d), fecha_hasta: fmtDate(today) };
    }
    case "mes_actual":
      return {
        preset,
        fecha_desde: fmtDate(startOfMonth),
        fecha_hasta: fmtDate(today),
      };
  }
}

interface DashboardFiltersProps {
  range: DashboardRange;
  onRangeChange: (range: DashboardRange) => void;
  sucursalId: number | null;
  onSucursalChange: (id: number | null) => void;
  sucursales: Sucursal[] | undefined;
}

export function DashboardFilters({
  range,
  onRangeChange,
  sucursalId,
  onSucursalChange,
  sucursales,
}: DashboardFiltersProps) {
  const sucursalLabel = React.useMemo(() => {
    if (sucursalId === null) return "Todas las sucursales";
    const s = sucursales?.find((x) => x.id === sucursalId);
    return s ? `${s.codigo} · ${s.nombre}` : "Sucursal";
  }, [sucursalId, sucursales]);

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Período */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <Calendar className="h-4 w-4" strokeWidth={1.5} />
            <span className="font-medium">{PRESET_LABELS[range.preset]}</span>
            <ChevronDown className="h-3.5 w-3.5 opacity-60" strokeWidth={1.5} />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[200px]">
          <DropdownMenuLabel>Período</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {(Object.keys(PRESET_LABELS) as PeriodPreset[]).map((preset) => (
            <DropdownMenuItem
              key={preset}
              onSelect={() => onRangeChange(resolvePreset(preset))}
              className={
                range.preset === preset
                  ? "bg-muted/60 font-medium text-foreground"
                  : ""
              }
            >
              {PRESET_LABELS[preset]}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Sucursal */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <StoreIcon className="h-4 w-4" strokeWidth={1.5} />
            <span className="font-medium truncate max-w-[200px]">
              {sucursalLabel}
            </span>
            <ChevronDown className="h-3.5 w-3.5 opacity-60" strokeWidth={1.5} />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[220px]">
          <DropdownMenuLabel>Sucursal</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => onSucursalChange(null)}
            className={
              sucursalId === null
                ? "bg-muted/60 font-medium text-foreground"
                : ""
            }
          >
            <Filter className="h-4 w-4 opacity-60" strokeWidth={1.5} />
            Todas las sucursales
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {sucursales
            ?.filter((s) => s.activa)
            .map((s) => (
              <DropdownMenuItem
                key={s.id}
                onSelect={() => onSucursalChange(s.id)}
                className={
                  sucursalId === s.id
                    ? "bg-muted/60 font-medium text-foreground"
                    : ""
                }
              >
                <span className="font-mono text-[11px] rounded-md bg-muted/60 px-1.5 py-0.5 text-muted-foreground">
                  {s.codigo}
                </span>
                <span className="truncate">{s.nombre}</span>
              </DropdownMenuItem>
            ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
