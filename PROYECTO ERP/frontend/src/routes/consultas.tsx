/**
 * Pantalla "Consultas" — equivalente al F3 del sistema viejo.
 *
 * Sidebar con entidades a la izquierda, panel con filtros + tabla + export
 * a la derecha. Cada entidad define sus propias columnas y filtros.
 */
import * as React from "react";
import { createRoute } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownToLine,
  Boxes,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Download,
  FileText,
  Loader2,
  Package,
  Receipt,
  Search,
  ShieldCheck,
  ShoppingCart,
  Truck,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
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
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { listSucursales } from "@/api/sucursales";
import {
  downloadConsultaXlsx,
  listConsulta,
  type ConsultaParams,
  type EntidadConsulta,
} from "@/api/consultas";
import { requireAccess } from "@/lib/permissions";
import { appLayoutRoute } from "./app-layout";

export const consultasRoute = createRoute({
  getParentRoute: () => appLayoutRoute,
  path: "/consultas",
  beforeLoad: requireAccess("/consultas"),
  component: ConsultasPage,
});

interface FieldDef {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  format?: "money" | "date" | "datetime";
}

interface FilterDef {
  type: "search" | "date_range" | "sucursal" | "select" | "number";
  key: string;
  label: string;
  placeholder?: string;
  options?: { value: string; label: string }[];
}

interface EntidadConfig {
  id: EntidadConsulta;
  label: string;
  icon: LucideIcon;
  description: string;
  fields: FieldDef[];
  filters: FilterDef[];
  defaultDateRange?: boolean;
}

const ENTIDADES_CONFIG: EntidadConfig[] = [
  {
    id: "clientes",
    label: "Clientes",
    icon: Users,
    description: "Buscá por código, razón social o CUIT.",
    fields: [
      { key: "codigo", label: "Código" },
      { key: "razon_social", label: "Razón social" },
      { key: "cuit", label: "CUIT" },
      { key: "condicion_iva", label: "Cond. IVA" },
      { key: "saldo", label: "Saldo", format: "money", align: "right" },
      { key: "email", label: "Email" },
      { key: "telefono", label: "Teléfono" },
    ],
    filters: [{ type: "search", key: "q", label: "Buscar", placeholder: "Razón social, CUIT…" }],
  },
  {
    id: "proveedores",
    label: "Proveedores",
    icon: Truck,
    description: "Listado de proveedores activos.",
    fields: [
      { key: "codigo", label: "Código" },
      { key: "razon_social", label: "Razón social" },
      { key: "cuit", label: "CUIT" },
      { key: "email", label: "Email" },
      { key: "telefono", label: "Teléfono" },
    ],
    filters: [{ type: "search", key: "q", label: "Buscar", placeholder: "Razón social, CUIT…" }],
  },
  {
    id: "articulos",
    label: "Artículos",
    icon: Package,
    description: "Catálogo completo con costos y precios.",
    fields: [
      { key: "codigo", label: "Código" },
      { key: "descripcion", label: "Descripción" },
      { key: "unidad_medida", label: "Unidad" },
      { key: "costo", label: "Costo", format: "money", align: "right" },
      { key: "pvp_base", label: "PVP", format: "money", align: "right" },
    ],
    filters: [
      { type: "search", key: "q", label: "Buscar", placeholder: "Código, descripción, código de barras…" },
      {
        type: "select",
        key: "activo",
        label: "Estado",
        options: [
          { value: "", label: "Todos" },
          { value: "true", label: "Activos" },
          { value: "false", label: "Inactivos" },
        ],
      },
    ],
  },
  {
    id: "ventas",
    label: "Ventas",
    icon: Receipt,
    description: "Facturas y tickets emitidos en el período.",
    fields: [
      { key: "fecha", label: "Fecha", format: "date" },
      { key: "tipo", label: "Tipo" },
      { key: "numero", label: "N°", align: "right" },
      { key: "sucursal", label: "Sucursal" },
      { key: "cliente", label: "Cliente" },
      { key: "total", label: "Total", format: "money", align: "right" },
    ],
    defaultDateRange: true,
    filters: [
      { type: "search", key: "q", label: "Cliente / CUIT", placeholder: "Buscar…" },
      { type: "date_range", key: "fecha", label: "Período" },
      { type: "sucursal", key: "sucursal_id", label: "Sucursal" },
    ],
  },
  {
    id: "compras",
    label: "Compras",
    icon: ShoppingCart,
    description: "Compras a proveedores (factura tipo C).",
    fields: [
      { key: "fecha", label: "Fecha", format: "date" },
      { key: "comprobante", label: "Comprobante" },
      { key: "proveedor", label: "Proveedor" },
      { key: "cuit", label: "CUIT" },
      { key: "sucursal", label: "Sucursal" },
      { key: "total", label: "Total", format: "money", align: "right" },
    ],
    defaultDateRange: true,
    filters: [
      { type: "date_range", key: "fecha", label: "Período" },
      { type: "sucursal", key: "sucursal_id", label: "Sucursal" },
    ],
  },
  {
    id: "cobranzas",
    label: "Cobranzas",
    icon: Wallet,
    description: "Pagos recibidos de clientes.",
    fields: [
      { key: "fecha", label: "Fecha", format: "date" },
      { key: "cliente", label: "Cliente" },
      { key: "factura_ref", label: "Factura ref." },
      { key: "monto", label: "Monto", format: "money", align: "right" },
      { key: "medio", label: "Medio" },
      { key: "sucursal", label: "Sucursal" },
    ],
    defaultDateRange: true,
    filters: [
      { type: "date_range", key: "fecha", label: "Período" },
      { type: "sucursal", key: "sucursal_id", label: "Sucursal" },
    ],
  },
  {
    id: "pagos",
    label: "Pagos",
    icon: CreditCard,
    description: "Pagos a proveedores.",
    fields: [
      { key: "fecha", label: "Fecha", format: "date" },
      { key: "proveedor", label: "Proveedor" },
      { key: "factura_ref", label: "Factura ref." },
      { key: "monto", label: "Monto", format: "money", align: "right" },
      { key: "medio", label: "Medio" },
      { key: "sucursal", label: "Sucursal" },
    ],
    defaultDateRange: true,
    filters: [
      { type: "date_range", key: "fecha", label: "Período" },
      { type: "sucursal", key: "sucursal_id", label: "Sucursal" },
    ],
  },
  {
    id: "movimientos",
    label: "Movimientos",
    icon: ArrowDownToLine,
    description: "Ledger universal: ventas, cobranzas, pagos, ajustes.",
    fields: [
      { key: "fecha", label: "Fecha", format: "date" },
      { key: "tipo", label: "Tipo" },
      { key: "monto", label: "Monto", format: "money", align: "right" },
      { key: "medio", label: "Medio" },
      { key: "sucursal", label: "Sucursal" },
      { key: "descripcion", label: "Descripción" },
    ],
    defaultDateRange: true,
    filters: [
      { type: "date_range", key: "fecha", label: "Período" },
      { type: "sucursal", key: "sucursal_id", label: "Sucursal" },
      {
        type: "select",
        key: "tipo",
        label: "Tipo",
        options: [
          { value: "", label: "Todos" },
          { value: "venta", label: "Venta" },
          { value: "cobranza", label: "Cobranza" },
          { value: "pago_proveedor", label: "Pago a proveedor" },
          { value: "ingreso_efectivo", label: "Ingreso efectivo" },
          { value: "egreso_efectivo", label: "Egreso efectivo" },
          { value: "ajuste", label: "Ajuste" },
        ],
      },
    ],
  },
  {
    id: "stock-bajo",
    label: "Stock bajo",
    icon: Boxes,
    description: "Artículos con cantidad menor al mínimo configurado.",
    fields: [
      { key: "codigo", label: "Código" },
      { key: "descripcion", label: "Descripción" },
      { key: "sucursal", label: "Sucursal" },
      { key: "cantidad", label: "Cantidad", align: "right" },
      { key: "valor", label: "Valor", format: "money", align: "right" },
    ],
    filters: [
      { type: "sucursal", key: "sucursal_id", label: "Sucursal" },
      { type: "number", key: "minimo", label: "Umbral mínimo", placeholder: "5" },
    ],
  },
  {
    id: "caes",
    label: "CAEs emitidos",
    icon: ShieldCheck,
    description: "Códigos de Autorización Electrónica AFIP.",
    fields: [
      { key: "fecha_emision", label: "Emisión", format: "date" },
      { key: "cae", label: "CAE" },
      { key: "tipo_afip", label: "Tipo AFIP", align: "right" },
      { key: "numero", label: "N°", align: "right" },
      { key: "fecha_vencimiento", label: "Vence", format: "date" },
      { key: "resultado", label: "Resultado" },
      { key: "sucursal", label: "Sucursal" },
    ],
    defaultDateRange: true,
    filters: [{ type: "date_range", key: "fecha", label: "Período" }],
  },
  {
    id: "alertas",
    label: "Alertas",
    icon: AlertTriangle,
    description: "Inconsistencias detectadas automáticamente.",
    fields: [
      { key: "detected_at", label: "Detectada", format: "date" },
      { key: "tipo", label: "Tipo" },
      { key: "severidad", label: "Severidad" },
      { key: "estado", label: "Estado" },
      { key: "titulo", label: "Título" },
      { key: "sucursal", label: "Sucursal" },
    ],
    filters: [
      {
        type: "select",
        key: "estado",
        label: "Estado",
        options: [
          { value: "", label: "Todas" },
          { value: "nueva", label: "Nuevas" },
          { value: "en_revision", label: "En revisión" },
          { value: "confirmada", label: "Confirmadas" },
          { value: "resuelta", label: "Resueltas" },
          { value: "descartada", label: "Descartadas" },
        ],
      },
      {
        type: "select",
        key: "severidad",
        label: "Severidad",
        options: [
          { value: "", label: "Todas" },
          { value: "baja", label: "Baja" },
          { value: "media", label: "Media" },
          { value: "alta", label: "Alta" },
          { value: "critica", label: "Crítica" },
        ],
      },
    ],
  },
];

const PER_PAGE = 25;

function fmtDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function defaultLast30(): { from: string; to: string } {
  const today = new Date();
  const past = new Date(today);
  past.setDate(today.getDate() - 30);
  return { from: fmtDate(past), to: fmtDate(today) };
}

function fmtMoney(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "string" ? parseFloat(v) : Number(v);
  if (!Number.isFinite(n)) return String(v);
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function fmtCell(value: unknown, format?: FieldDef["format"]): string {
  if (value === null || value === undefined || value === "") return "—";
  if (format === "money") return fmtMoney(value);
  if (format === "date" && typeof value === "string") return value.slice(0, 10);
  if (format === "datetime" && typeof value === "string") {
    return value.length > 19 ? value.slice(0, 16).replace("T", " ") : value;
  }
  return String(value);
}

function ConsultasPage() {
  const [activeId, setActiveId] = React.useState<EntidadConsulta>("clientes");
  const active = ENTIDADES_CONFIG.find((e) => e.id === activeId)!;

  return (
    <div className="flex flex-col gap-6 max-w-[1400px]">
      <div>
        <h2 className="text-[28px] font-semibold tracking-tight leading-tight">
          Consultas
        </h2>
        <p className="mt-1.5 text-[14px] text-muted-foreground">
          Buscá, filtrá y exportá información del sistema.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">
        {/* Sidebar de entidades */}
        <Card className="p-2 self-start">
          <nav className="flex flex-col gap-0.5">
            {ENTIDADES_CONFIG.map((e) => {
              const Icon = e.icon;
              const selected = e.id === activeId;
              return (
                <button
                  key={e.id}
                  onClick={() => setActiveId(e.id)}
                  className={cn(
                    "flex items-center gap-3 rounded-[8px] px-3 py-2 text-left text-[13px] font-medium transition-colors duration-200 ease-apple",
                    selected
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
                  )}
                >
                  <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
                  <span>{e.label}</span>
                </button>
              );
            })}
          </nav>
        </Card>

        {/* Panel principal */}
        <ConsultaPanel key={active.id} entidad={active} />
      </div>
    </div>
  );
}

interface PanelProps {
  entidad: EntidadConfig;
}

function ConsultaPanel({ entidad }: PanelProps) {
  const sucursalesQ = useQuery({
    queryKey: ["sucursales"],
    queryFn: listSucursales,
    staleTime: 60_000,
  });

  const [filters, setFilters] = React.useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    if (entidad.defaultDateRange) {
      const r = defaultLast30();
      init.fecha_desde = r.from;
      init.fecha_hasta = r.to;
    }
    return init;
  });

  const [page, setPage] = React.useState(1);

  const queryParams = React.useMemo<ConsultaParams>(() => {
    const params: ConsultaParams = { page, per_page: PER_PAGE };
    for (const [k, v] of Object.entries(filters)) {
      if (!v) continue;
      if (k === "sucursal_id") {
        const n = parseInt(v, 10);
        if (Number.isFinite(n)) params.sucursal_id = n;
      } else if (k === "minimo") {
        const n = parseInt(v, 10);
        if (Number.isFinite(n)) params.minimo = n;
      } else {
        (params as Record<string, string>)[k] = v;
      }
    }
    return params;
  }, [filters, page]);

  const dataQ = useQuery({
    queryKey: ["consulta", entidad.id, queryParams],
    queryFn: () => listConsulta(entidad.id, queryParams),
    placeholderData: keepPreviousData,
  });

  const setFilter = React.useCallback((key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }, []);

  const { toast } = useToast();
  const [exporting, setExporting] = React.useState(false);

  const handleExport = React.useCallback(async () => {
    setExporting(true);
    try {
      // Sin paginación para el Excel
      const fullParams = { ...queryParams };
      delete fullParams.page;
      delete fullParams.per_page;
      await downloadConsultaXlsx(entidad.id, fullParams);
      toast({
        title: "Exportación lista",
        description: `${entidad.label} se descargó correctamente.`,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error al exportar";
      toast({
        title: "Error al exportar",
        description: message,
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  }, [entidad, queryParams, toast]);

  const total = dataQ.data?.total ?? 0;
  const pages = dataQ.data?.pages ?? 1;
  const items = dataQ.data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      {/* Header del panel */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-[18px] font-semibold tracking-tight leading-tight">
            {entidad.label}
          </h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            {entidad.description}
          </p>
        </div>
        <Button
          onClick={handleExport}
          disabled={exporting || total === 0}
          variant="outline"
          size="sm"
        >
          {exporting ? (
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
          ) : (
            <Download className="h-4 w-4" strokeWidth={1.5} />
          )}
          Exportar Excel
        </Button>
      </div>

      {/* Filtros */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {entidad.filters.map((f) => (
            <FilterField
              key={f.key}
              filter={f}
              value={filters}
              onChange={setFilter}
              sucursales={sucursalesQ.data}
            />
          ))}
        </div>
      </Card>

      {/* Tabla */}
      <Card className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              {entidad.fields.map((f) => (
                <TableHead
                  key={f.key}
                  className={f.align === "right" ? "text-right" : undefined}
                >
                  {f.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {dataQ.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={`skeleton-${i}`}>
                  {entidad.fields.map((f) => (
                    <TableCell key={f.key}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={entidad.fields.length}
                  className="text-center text-muted-foreground py-8"
                >
                  Sin resultados
                </TableCell>
              </TableRow>
            ) : (
              items.map((row, idx) => (
                <TableRow key={`row-${idx}`}>
                  {entidad.fields.map((f) => {
                    const value = row[f.key];
                    return (
                      <TableCell
                        key={f.key}
                        className={cn(
                          f.align === "right" ? "text-right tabular-nums" : "",
                          f.format === "money" ? "tabular-nums" : "",
                        )}
                      >
                        {fmtCell(value, f.format)}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Footer paginación */}
      <div className="flex items-center justify-between">
        <span className="text-[12px] text-muted-foreground">
          {total === 0
            ? "Sin resultados"
            : `${total.toLocaleString("es-AR")} resultado${total === 1 ? "" : "s"}`}
        </span>
        {pages > 1 && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              <ChevronLeft className="h-4 w-4" strokeWidth={1.5} />
              Anterior
            </Button>
            <span className="text-[12px] text-muted-foreground tabular-nums">
              {page} / {pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages}
            >
              Siguiente
              <ChevronRight className="h-4 w-4" strokeWidth={1.5} />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

interface FilterFieldProps {
  filter: FilterDef;
  value: Record<string, string>;
  onChange: (key: string, value: string) => void;
  sucursales:
    | { id: number; codigo: string; nombre: string; activa: boolean }[]
    | undefined;
}

function FilterField({ filter, value, onChange, sucursales }: FilterFieldProps) {
  if (filter.type === "search") {
    return (
      <div className="flex flex-col gap-1.5">
        <Label>{filter.label}</Label>
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
            strokeWidth={1.5}
          />
          <Input
            placeholder={filter.placeholder}
            value={value[filter.key] ?? ""}
            onChange={(e) => onChange(filter.key, e.target.value)}
            className="pl-9"
          />
        </div>
      </div>
    );
  }

  if (filter.type === "date_range") {
    return (
      <>
        <div className="flex flex-col gap-1.5">
          <Label>Desde</Label>
          <Input
            type="date"
            value={value.fecha_desde ?? ""}
            onChange={(e) => onChange("fecha_desde", e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Hasta</Label>
          <Input
            type="date"
            value={value.fecha_hasta ?? ""}
            onChange={(e) => onChange("fecha_hasta", e.target.value)}
          />
        </div>
      </>
    );
  }

  if (filter.type === "sucursal") {
    const items = (sucursales ?? []).filter((s) => s.activa);
    return (
      <div className="flex flex-col gap-1.5">
        <Label>{filter.label}</Label>
        <select
          value={value[filter.key] ?? ""}
          onChange={(e) => onChange(filter.key, e.target.value)}
          className="flex h-10 w-full rounded-[8px] border border-input bg-background px-3 py-2 text-sm text-foreground transition-colors duration-200 ease-apple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
        >
          <option value="">Todas las sucursales</option>
          {items.map((s) => (
            <option key={s.id} value={s.id}>
              {s.codigo} · {s.nombre}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (filter.type === "select") {
    return (
      <div className="flex flex-col gap-1.5">
        <Label>{filter.label}</Label>
        <select
          value={value[filter.key] ?? ""}
          onChange={(e) => onChange(filter.key, e.target.value)}
          className="flex h-10 w-full rounded-[8px] border border-input bg-background px-3 py-2 text-sm text-foreground transition-colors duration-200 ease-apple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
        >
          {(filter.options ?? []).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (filter.type === "number") {
    return (
      <div className="flex flex-col gap-1.5">
        <Label>{filter.label}</Label>
        <Input
          type="number"
          placeholder={filter.placeholder}
          value={value[filter.key] ?? ""}
          onChange={(e) => onChange(filter.key, e.target.value)}
        />
      </div>
    );
  }

  // Avoid unused-import lint
  void Loader2;
  void FileText;
  return null;
}
